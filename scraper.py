from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright
from tenacity import (RetryError, retry, retry_if_exception_type,
                      stop_after_attempt, wait_exponential)

import config
from models import Document, ExtractionResults, LetterBucket, Product, Substance
from utils import (collect_links, ensure_disclaimer_acknowledged,
                   normalise_whitespace, parse_active_substances,
                   parse_file_size, resolve_url)

logger = logging.getLogger("MHRAExtractor")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")


class NavigationFailure(Exception):
    """Raised when the browser fails to navigate to a page after retries."""


@dataclass
class ScrapeStatistics:
    total_letters: int = 0
    total_substances: int = 0
    total_products: int = 0
    total_documents: int = 0


class MHRAExtractor:
    def __init__(
        self,
        *,
        headless: bool = config.DEFAULT_HEADLESS,
        request_delay: float = config.REQUEST_DELAY_SECONDS,
        console=None,
        progress=None,
        progress_tasks: Optional[Dict[str, int]] = None,
    ) -> None:
        self.headless = headless
        self.request_delay = request_delay
        self.generated_at = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.letters: List[LetterBucket] = []
        self.pdf_links: List[dict] = []
        self.stats = ScrapeStatistics(total_letters=len(config.LETTERS))
        self.console = console
        self.progress = progress
        self.progress_tasks: Dict[str, int] = progress_tasks or {}

    async def __aenter__(self) -> "MHRAExtractor":
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()
        self.page.set_default_timeout(config.NAVIGATION_TIMEOUT_MS)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def run(self) -> Tuple[ExtractionResults, List[dict], ScrapeStatistics]:
        for letter in config.LETTERS:
            logger.info("Processing letter %s", letter)
            self._log(f"[bold cyan]Letter[/bold cyan]: {letter}")
            self._progress_set_description("letters", f"Letter {letter}")
            letter_bucket = await self._process_letter(letter)
            self.letters.append(letter_bucket)
            self._progress_advance("letters")
        results = ExtractionResults(
            letters=self.letters,
            generated_at_utc=self.generated_at,
            source=config.BASE_URL,
        )
        return results, self.pdf_links, self.stats

    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(PlaywrightTimeoutError),
        reraise=True,
    )
    async def _navigate(self, url: str) -> None:
        logger.debug("Navigating to %s", url)
        response = await self.page.goto(url, wait_until="domcontentloaded")
        if response and response.status >= 400:
            raise PlaywrightTimeoutError(f"HTTP {response.status} for {url}")
        await self.page.wait_for_load_state("networkidle")

    async def _process_letter(self, letter: str) -> LetterBucket:
        bucket = LetterBucket(letter=letter)
        url = resolve_url(config.BASE_URL, config.SUBSTANCE_INDEX_PATH.format(letter=letter))
        try:
            await self._navigate(url)
        except RetryError as retry_error:
            raise NavigationFailure(f"Failed to load letter index {letter}") from retry_error

        try:
            await self.page.wait_for_selector("nav ul li a[href^='/substance/']", timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning("No substances found for letter %s", letter)
            self._log(f"[yellow]No substances found for letter {letter}[/yellow]")
            return bucket

        substances = await collect_links(self.page, "nav ul li.substance-name a", "/substance/")
        if not substances:
            substances = await collect_links(self.page, "nav ul li a", "/substance/")

        self._progress_prepare(
            "substances",
            len(substances),
            f"Substances for letter {letter} ({len(substances)} total)",
        )
        self._log(f"[cyan]Substances[/cyan]: {len(substances)} for letter {letter}")

        for substance_entry in substances:
            name = substance_entry["text"]
            self._progress_set_description("substances", f"Substance: {name}")
            self._log(f"  [cyan]Substance[/cyan]: {name}")
            relative_url = substance_entry["href"]
            bucket.substances.append(await self._process_substance(name, relative_url))
            self.stats.total_substances += 1
            self._progress_advance("substances")
            await asyncio.sleep(self.request_delay)
        return bucket

    async def _process_substance(self, name: str, relative_url: str) -> Substance:
        substance = Substance(name=name, substance_url=relative_url)
        url = resolve_url(config.BASE_URL, relative_url)
        try:
            await self._navigate(url)
        except RetryError as retry_error:
            logger.error("Failed to load substance %s", name)
            return substance

        try:
            await self.page.wait_for_selector("nav ul li a[href^='/product/']", timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning("No products found for substance %s", name)
            self._log(f"[yellow]No products found for substance {name}[/yellow]")
            return substance

        products = await collect_links(self.page, "nav ul li.product-name a", "/product/")
        if not products:
            products = await collect_links(self.page, "nav ul li a", "/product/")

        self._progress_prepare(
            "products",
            len(products),
            f"Products for {name} ({len(products)} total)",
        )
        self._log(f"[green]Products[/green]: {len(products)} for substance {name}")

        for product_entry in products:
            label = product_entry["text"]
            self._progress_set_description("products", f"Product: {label}")
            self._log(f"    [green]Product[/green]: {label}")
            relative_product_url = product_entry["href"]
            product = await self._process_product(label, relative_product_url)
            substance.products.append(product)
            self.stats.total_products += 1
            self._progress_advance("products")
            await asyncio.sleep(self.request_delay)
        return substance

    async def _process_product(self, label: str, relative_url: str) -> Product:
        product = Product(label=label, product_url=relative_url)
        url = resolve_url(config.BASE_URL, relative_url)
        try:
            await self._navigate(url)
        except (RetryError, PlaywrightTimeoutError) as error:
            logger.error("Failed to load product %s", label)
            self._log(f"[red]Failed to load product {label}: {error}[/red]")
            return product

        await ensure_disclaimer_acknowledged(self.page)

        try:
            await self.page.wait_for_selector("section.column.results", timeout=5000)
        except PlaywrightTimeoutError:
            logger.info("No documents displayed for product %s", label)
            return product

        results_locator = self.page.locator("section.column.results div.search-result")
        count = await results_locator.count()

        self._progress_prepare(
            "documents",
            count,
            f"Documents for {label} ({count} total)",
        )
        self._log(f"[magenta]Documents[/magenta]: {count} for product {label}")

        for index in range(count):
            result = results_locator.nth(index)
            doc_anchor = result.locator("dd.right a").first
            doc_href = await doc_anchor.get_attribute("href")
            if not doc_href:
                continue

            doc_url = resolve_url(config.BASE_URL, doc_href)

            doc_type_element = result.locator("dt.left p.icon")
            doc_type = normalise_whitespace(await doc_type_element.first.inner_text()) if await doc_type_element.count() else ""

            title_element = result.locator("dd.right a p.title")
            title = normalise_whitespace(await title_element.first.inner_text()) if await title_element.count() else label

            subtitle_element = result.locator("dd.right a p.subtitle")
            subtitle = normalise_whitespace(await subtitle_element.first.inner_text()) if await subtitle_element.count() else None

            metadata_entries = await result.locator("dd.right p.metadata").all_inner_texts()
            file_size_kb = None
            active_substances = []
            for metadata in metadata_entries:
                metadata_clean = normalise_whitespace(metadata)
                if "file size" in metadata_clean.lower():
                    file_size_kb = parse_file_size(metadata_clean)
                if "active substances" in metadata_clean.lower():
                    active_substances = parse_active_substances(metadata_clean)

            document = Document(
                doc_url=doc_url,
                doc_type=doc_type,
                title=title,
                subtitle=subtitle,
                file_size_kb=file_size_kb,
                active_substances=active_substances,
                product_label=label,
                product_url=relative_url,
            )
            self._progress_set_description("documents", f"Document: {subtitle or title}")
            product.documents.append(document)
            self.pdf_links.append(document.to_pdf_link_entry())
            self.stats.total_documents += 1
            self._progress_advance("documents")
            self._log(f"      [magenta]Document[/magenta]: {subtitle or title} ({doc_type})")

        return product

    def _progress_set_description(self, key: str, description: str) -> None:
        if not self.progress:
            return
        task_id = self.progress_tasks.get(key)
        if task_id is None:
            return
        try:
            self.progress.update(task_id, description=description)
        except Exception:  # pragma: no cover - progress failures should not break extraction
            logger.debug("Failed updating progress description for %s", key, exc_info=True)

    def _progress_advance(self, key: str, amount: int = 1) -> None:
        if not self.progress or amount == 0:
            return
        task_id = self.progress_tasks.get(key)
        if task_id is None:
            return
        try:
            self.progress.advance(task_id, amount)
        except Exception:  # pragma: no cover
            logger.debug("Failed advancing progress for %s", key, exc_info=True)

    def _progress_prepare(self, key: str, total: int, description: str) -> None:
        if not self.progress:
            return
        task_id = self.progress_tasks.get(key)
        if task_id is None:
            return
        try:
            self.progress.update(task_id, total=total or 0, completed=0, description=description)
        except Exception:  # pragma: no cover
            logger.debug("Failed preparing progress for %s", key, exc_info=True)

    def _log(self, message: str) -> None:
        if self.console:
            try:
                self.console.log(message)
                return
            except Exception:  # pragma: no cover
                logger.debug("Console logging failed for message %s", message, exc_info=True)
        logger.info(message)


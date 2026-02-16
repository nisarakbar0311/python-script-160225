from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from playwright.async_api import Page


def normalise_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_file_size(metadata_text: str) -> Optional[int]:
    match = re.search(r"file size\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*(kb|mb)", metadata_text, re.IGNORECASE)
    if not match:
        return None
    size_value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "kb":
        return int(round(size_value))
    if unit == "mb":
        return int(round(size_value * 1024))
    return None


def parse_active_substances(metadata_text: str) -> List[str]:
    match = re.search(r"active substances\s*:\s*(.+)", metadata_text, re.IGNORECASE)
    if not match:
        return []
    payload = match.group(1)
    parts = re.split(r",|;", payload)
    return [normalise_whitespace(part) for part in parts if normalise_whitespace(part)]


def resolve_url(base_url: str, relative_url: str) -> str:
    return urljoin(base_url, relative_url)


async def ensure_disclaimer_acknowledged(page: Page) -> None:
    checkbox = page.locator("#agree-checkbox")
    if await checkbox.count() == 0:
        return
    await checkbox.scroll_into_view_if_needed()
    await checkbox.check()
    await page.wait_for_selector("button[type='submit']:not([disabled])")
    button = page.locator("button[type='submit']:not([disabled])")
    await button.click()
    await page.wait_for_load_state("networkidle")


async def collect_links(page: Page, selector: str, href_prefix: Optional[str] = None) -> List[dict]:
    elements = page.locator(selector)
    count = await elements.count()
    results: List[dict] = []
    for index in range(count):
        element = elements.nth(index)
        href = await element.get_attribute("href")
        if not href:
            continue
        if href_prefix and not href.startswith(href_prefix):
            continue
        text = normalise_whitespace(await element.inner_text())
        if not text:
            continue
        results.append({"text": text, "href": href})
    return results


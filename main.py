from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

import config
from scraper import MHRAExtractor, NavigationFailure


def ensure_directories() -> None:
    config.LATEST_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)


def get_next_version_directory() -> Path:
    config.PUBLIC_PATH.mkdir(parents=True, exist_ok=True)
    existing_versions = []
    for candidate in config.PUBLIC_PATH.iterdir():
        if not candidate.is_dir():
            continue
        if not candidate.name.startswith(config.OUTPUT_VERSION_PREFIX):
            continue
        suffix = candidate.name.replace(config.OUTPUT_VERSION_PREFIX, "").strip()
        if suffix.isdigit():
            existing_versions.append(int(suffix))
    next_index = max(existing_versions, default=0) + 1
    version_dir = config.PUBLIC_PATH / f"{config.OUTPUT_VERSION_PREFIX}{next_index}"
    version_dir.mkdir(parents=True, exist_ok=True)
    return version_dir


def write_json(target: Path, data: dict) -> None:
    with target.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def build_update_certificate(stats: dict, version_label: str, generated_at: str) -> dict:
    return {
        "update_version": version_label,
        "update_timestamp": generated_at,
        "statistics": {
            "total_letters": stats.get("total_letters", 0),
            "total_substances": stats.get("total_substances", 0),
            "total_products": stats.get("total_products", 0),
            "total_pdfs": stats.get("total_documents", 0),
            "new_pdfs": stats.get("total_documents", 0),
            "updated_pdfs": 0,
            "unchanged_pdfs": 0,
        },
        "files_generated": [
            "mhra_ultra_3.0.json - Hierarchical structure (letters > substances > products > documents)",
            "all_pdf_links.json - Flat list of all PDF links",
            "mhra_structure_mapping.json - Folder structure mapping",
            "update_certificate.json - Run summary and statistics",
        ],
        "note": "Data extracted using the automated Playwright crawler.",
    }


async def execute_scrape(headless: bool, request_delay: float, version_label: str, base_path: str) -> None:
    ensure_directories()
    version_directory = get_next_version_directory()

    console = Console()
    progress = Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

    tasks = {}
    with progress:
        tasks["letters"] = progress.add_task("Letters", total=len(config.LETTERS))
        tasks["substances"] = progress.add_task("Substances", total=None)
        tasks["products"] = progress.add_task("Products", total=None)
        tasks["documents"] = progress.add_task("Documents", total=None)

        async with MHRAExtractor(
            headless=headless,
            request_delay=request_delay,
            console=console,
            progress=progress,
            progress_tasks=tasks,
        ) as extractor:
            try:
                extraction_results, pdf_links, stats = await extractor.run()
            except NavigationFailure as error:
                console.print(f"[red]Navigation failure:[/red] {error}")
                raise SystemExit(1) from error

    mhra_ultra_payload = extraction_results.to_mhra_ultra()
    structure_mapping_payload = extraction_results.to_structure_mapping(base_path)

    stats_payload = {
        "total_letters": stats.total_letters,
        "total_substances": stats.total_substances,
        "total_products": stats.total_products,
        "total_documents": stats.total_documents,
    }

    certificate_payload = build_update_certificate(stats_payload, version_label, extraction_results.generated_at_utc)

    latest_targets = {
        config.GENERATED_FILES["mhra_ultra"]: mhra_ultra_payload,
        config.GENERATED_FILES["pdf_links"]: {
            "generated_at_utc": extraction_results.generated_at_utc,
            "source": config.BASE_URL,
            "total_pdf_links": stats.total_documents,
            "pdf_links": pdf_links,
        },
        config.GENERATED_FILES["structure"]: structure_mapping_payload,
        config.GENERATED_FILES["certificate"]: certificate_payload,
    }

    for filename, payload in latest_targets.items():
        destination = config.LATEST_OUTPUT_PATH / filename
        write_json(destination, payload)

    for filename in latest_targets.keys():
        source = config.LATEST_OUTPUT_PATH / filename
        shutil.copy2(source, version_directory / filename)

    console.print("[green]Extraction complete.[/green]")
    console.print(f"[cyan]Latest dataset updated at:[/cyan] {config.LATEST_OUTPUT_PATH}")
    console.print(f"[cyan]Version snapshot stored at:[/cyan] {version_directory}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated extraction system for the MHRA products database.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless mode to watch the browser.")
    parser.add_argument(
        "--request-delay",
        type=float,
        default=config.REQUEST_DELAY_SECONDS,
        help="Delay in seconds between page navigations to be polite to the server.",
    )
    parser.add_argument(
        "--version-label",
        type=str,
        default=None,
        help="Version label stored in update_certificate.json. Defaults to 4.0.<DD.MM.YYYY>.",
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default=None,
        help="Base path reference included in mhra_structure_mapping.json metadata. Defaults to the project output folder.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    version_label: Optional[str] = args.version_label
    if version_label is None:
        today = datetime.now(tz=timezone.utc)
        version_label = f"4.0.{today.strftime('%d.%m.%Y')}"
    base_path: str = args.base_path if args.base_path is not None else str(config.LATEST_OUTPUT_PATH)
    asyncio.run(
        execute_scrape(
            headless=not args.no_headless,
            request_delay=args.request_delay,
            version_label=version_label,
            base_path=base_path,
        )
    )


if __name__ == "__main__":
    main()

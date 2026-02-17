from __future__ import annotations

from pathlib import Path

BASE_URL = "https://products.mhra.gov.uk"
SUBSTANCE_INDEX_PATH = "/substance-index/?letter={letter}"
LETTERS = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
]

# Root = Backend folder (where main.py and this config live)
BACKEND_PATH = Path(__file__).resolve().parent
# Generated files go in Backend/public (latest overwritten here; versioned in public/Version N)
PUBLIC_PATH = BACKEND_PATH / "public"
LATEST_OUTPUT_PATH = PUBLIC_PATH
OUTPUT_VERSION_PREFIX = "Version "
GENERATED_FILES = {
    "mhra_ultra": "mhra_ultra_3.0.json",
    "pdf_links": "all_pdf_links.json",
    "structure": "mhra_structure_mapping.json",
    "certificate": "update_certificate.json",
}

DEFAULT_HEADLESS = True
NAVIGATION_TIMEOUT_MS = 90000
REQUEST_DELAY_SECONDS = 0.15
MAX_RETRIES = 3


# MHRA Database Update System (Backend)

Python scraper that extracts pharmaceutical product data from the [MHRA UK website](https://products.mhra.gov.uk) and writes structured JSON outputs.

## How to run

### 1. Use a virtual environment (recommended)

From the **Backend** folder:

```bash
cd "/Users/nisarakbar/Downloads/MHRA database update system 2/Perfect Example/Backend"

# Create and activate a new venv (if you don’t have one)
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright’s Chromium browser (required for scraping)
playwright install chromium
```

### 2. Run the scraper

```bash
# Full run (headless, default delay between requests)
python main.py

# Watch the browser while it runs
python main.py --no-headless

# Slower run (e.g. 0.5 s delay between pages)
python main.py --request-delay 0.5

# Custom version label and base path for the mapping file
python main.py --version-label "4.0.manual" --base-path "/path/to/your/output"

# Upload generated files to Firebase Storage after extraction
python main.py --upload-to-firebase

# Test run: letter A only, 2 substances, 10 products per substance
python main.py --test
```

### 3. Where output goes

Generated files are written in the **`public`** folder inside the Backend folder (same folder as `main.py`):

- **Latest (overwritten each run):**  
  `Backend/public/` — the four JSON files are written here.
- **Versioned snapshots:**  
  `Backend/public/Version 1/`, `Backend/public/Version 2/`, … — each run also copies the files into the next version folder.

Generated files in each folder:

- `mhra_ultra_3.0.json` – full hierarchy (letters → substances → products → documents)
- `all_pdf_links.json` – flat list of all PDF links and metadata
- `mhra_structure_mapping.json` – folder-structure mapping
- `update_certificate.json` – run summary and statistics

## Options

| Option | Description |
|--------|-------------|
| `--no-headless` | Show the browser window while scraping |
| `--request-delay SECS` | Delay in seconds between page loads (default: 0.15) |
| `--version-label LABEL` | Label stored in `update_certificate.json` (default: `4.0.DD.MM.YYYY`) |
| `--base-path PATH` | Base path written into `mhra_structure_mapping.json` (default: latest output folder) |
| `--upload-to-firebase` | Upload generated JSON files to Firebase Storage after extraction |
| `--firebase-bucket NAME` | Firebase Storage bucket (overrides `FIREBASE_STORAGE_BUCKET` env var) |
| `--firebase-credentials PATH` | Path to service account JSON (overrides `GOOGLE_APPLICATION_CREDENTIALS`) |
| `--test` | Test run: letter A only, 2 substances, 10 products per substance (writes full file set to `public/`) |

## Firebase Storage upload

With `--upload-to-firebase`, the four generated JSON files are uploaded to Firebase Storage:

1. **Bucket:** Set `FIREBASE_STORAGE_BUCKET` (e.g. `your-project.appspot.com`) or use `--firebase-bucket`.
2. **Credentials:** Use a [Firebase service account key](https://firebase.google.com/docs/admin/setup#initialize-sdk) (JSON). Either set `GOOGLE_APPLICATION_CREDENTIALS` to its path, or pass `--firebase-credentials /path/to/serviceAccountKey.json`.
3. **Paths in Storage:** Latest: `{prefix}/latest/<filename>.json`; versioned: `{prefix}/{version_label}/<filename>.json`. Default prefix is `mhra`; set `FIREBASE_STORAGE_PREFIX` to change it.

Example:

```bash
export FIREBASE_STORAGE_BUCKET=your-project.appspot.com
export GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json
python main.py --upload-to-firebase
```

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt` (Playwright, BeautifulSoup, httpx, Pydantic, tenacity, rich, firebase-admin)

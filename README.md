# Invoice Reader

A small web app that reads invoices (PDF or image), extracts the key fields using the Claude API, and appends them to a Google Sheet — sorted by date.

Upload one or more invoices through a simple web page, and the app handles extraction, validation, and writing to your sheet automatically.

## What it does

1. Accepts multiple file uploads (PDF, JPG, PNG, JPEG, AVIF) through a web form.
2. Sends each file to the Claude API to extract structured data.
3. Validates and normalizes the results (consistent date format, defaults for missing fields).
4. Sorts the invoices by date.
5. Appends them as rows in a Google Sheet.

## Extracted fields

Each invoice is parsed into:

- `date`
- `seller`
- `price_excl_vat`
- `vat`
- `price_incl_vat`

## Tech stack

- **Backend:** Python, FastAPI
- **AI extraction:** Anthropic Claude API (PDFs via the Files API, images via base64)
- **Storage:** Google Sheets (via a service account)
- **Frontend:** Plain HTML, CSS, and JavaScript (`fetch`)

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/Eigirdas/invoice-reader.git
cd invoice-reader
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your secrets

These files are **not** included in the repo and must be added manually:

- **`.env`** — contains your Anthropic API key:
  ```
  ANTHROPIC_API_KEY=your_key_here
  ```
- **`invoice_secret.json`** — your Google service account credentials file.

Make sure the target Google Sheet is shared with the service account's email address.

### 4. Configure the spreadsheet

In `sheets.py`, set your spreadsheet ID and sheet range to match your own sheet.

## Running

Start the server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then open the app in a browser:

```
http://127.0.0.1:8000/
```

Using `--host 0.0.0.0` makes it reachable from other devices on the same network at `http://<machine-ip>:8000/`.

## Notes

- Invoices are processed in memory (no files are saved to disk).
- Processing is currently sequential — larger batches take proportionally longer.

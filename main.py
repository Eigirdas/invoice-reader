import anthropic
from config import ANTHROPIC_API_KEY
from langchain_anthropic import ChatAnthropic
import json
import base64
import os.path
from pathlib import Path
from datetime import datetime
from os import walk
from fastapi import FastAPI, UploadFile, File
from typing import List
from fastapi.responses import FileResponse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from sheets import create_session_sheet
from starlette.concurrency import run_in_threadpool
import asyncio
from fastapi import Header, HTTPException, Depends
from cleanup import cleanup_old_sheets

def verify_api_key(x_api_key: str = Header(...)):
    with open("secrets/api_keys.txt") as f:
        valid_keys = {line.strip() for line in f if line.strip()}
    if x_api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")


client = anthropic.Anthropic()

app = FastAPI()

llm = ChatAnthropic(
    model="claude-sonnet-4-6",
    api_key=ANTHROPIC_API_KEY
)



@app.get("/")
def home():
    return FileResponse("index.html")

@app.post("/uploadfiles")
async def upload(files: List[UploadFile] = File(...), _: None = Depends(verify_api_key)):
    file_bytes_list = [await f.read() for f in files]

    tasks = []
    filenames = []
    for data, file in zip(file_bytes_list, files):
        filenames.append(file.filename)
        if file.filename.endswith('.pdf'):
            tasks.append(run_in_threadpool(read_pdf_file, data, file.filename))
        else:
            tasks.append(run_in_threadpool(read_image_file, data, file.content_type))

    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = []
    failures = []
    for filename, result in zip(filenames, raw_results):
        if isinstance(result, Exception):
            print(f"Failed to process {filename}: {result}")
            failures.append({"filename": filename, "error": str(result)})
        else:
            successes.append(result)

    sheet_url = None
    sheet_error = None
    if successes:
        successes = validate_json_data(successes)
        sorted_json = sort_json_datafile(successes)
        try:
            sheet_url = await run_in_threadpool(create_session_sheet, sorted_json)
        except Exception as e:
            print(f"Failed to create session sheet: {e}")
            print(f"Extracted data (recover manually): {sorted_json}")
            sheet_error = str(e)
    else:
        sorted_json = []

    return {
        "Processed": len(sorted_json),
        "sheet_url": sheet_url,
        "sheet_error": sheet_error,
        "extracted_data": sorted_json if sheet_error else None,
        "failed": failures
    }


EXTRACTION_PROMPT = """Extract these fields and return ONLY valid JSON with double quotes:
{
    "date": "",
    "seller": "",
    "price_excl_vat": 0.0,
    "vat": 0.0,
    "price_incl_vat": 0.0
}

DATE RULES (important):
- Use the invoice ISSUE/transaction date — labelled "Išrašymo data", "Data", or "Kvito data". Do NOT use the print date labelled "Atspausdinta".
- Output strictly as DD/MM/YYYY.
- These invoices are from 2024 or later. Interpret 2-digit years accordingly: a date like "26-08-21" is YY-MM-DD = 21 August 2026, so output "21/08/2026". Never read it as the year 2021.
- If a full 4-digit date (e.g. "2026-08-21") also appears on the document, use it to confirm the correct year.
- If no date is found, return "date": null.

SELLER RULES:
- Use the seller/vendor company name (Lithuanian: "Pardavėjas"). If unclear, return "UNKNOWN".

Return ONLY the JSON object, no other text."""
""" For inside disk
def process_files(files):
    for file in files:
        if file.suffix == '.pdf':
            data = read_pdf_file(file)
            json_datafile.append(data)
        elif file.suffix in('.jpg','.png','.jpeg','.avif'):
            data = read_image_file(file)
            json_datafile.append(data)
"""


def validate_json_data(data):
    for json_data in data:
        json_data['date'] = parse_date(json_data['date']).strftime('%d/%m/%Y')
        if not isinstance(json_data['seller'],str):
            json_data['seller'] = "UNKNOWN"
        if not isinstance(json_data['price_excl_vat'],(int,float)):
            json_data['price_excl_vat'] = 0.0
        if not isinstance(json_data['vat'],(int,float)):
            json_data['vat'] = 0.0
        if not isinstance(json_data['price_incl_vat'],(int,float)):
            json_data['price_incl_vat'] = 0.0
    return data


def parse_date(date_str):
    if not date_str:
        print("Warning! Empty date")
        return datetime.min
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y'):
        try:
            parsed = datetime.strptime(date_str, fmt)
            if parsed.year < 2020:
                print(f"Warning! Suspicious year in '{date_str}'")
            return parsed
        except ValueError:
            continue
    print(f"Warning! Could not parse '{date_str}'")
    return datetime.min

def sort_json_datafile(data):
    return(sorted(data,key=lambda x:datetime.strptime(x['date'], '%d/%m/%Y')))

# Upload the PDF file
def read_pdf_file(file_bytes,file_name):

    pdf_upload = client.beta.files.upload(file=(file_name, file_bytes, "application/pdf"))

    # Use the uploaded file in a message
    pdf_message = client.beta.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        betas=["files-api-2025-04-14"],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "file", "file_id": pdf_upload.id},
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
    )
    pdf_response_text = pdf_message.content[0].text
    pdf_response_text = pdf_response_text.replace("```json", "").replace("```", "").strip()
    pdf_data = json.loads(pdf_response_text)
    return pdf_data

def read_image_file(file_bytes,media_type):

    # Upload the image file
    image_data = base64.standard_b64encode(file_bytes).decode("utf-8")

    # Use the uploaded file in a message
    photo_message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        }
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }
        ],
    )
    photo_response_text = photo_message.content[0].text
    photo_response_text = photo_response_text.replace("```json", "").replace("```", "").strip()
    photo_data = json.loads(photo_response_text)
    return photo_data

async def periodic_cleanup():
    while True:
        try:
            await run_in_threadpool(cleanup_old_sheets)
        except Exception as e:
            print(f"Cleanup failed: {e}")
        await asyncio.sleep(3600)

background_tasks = set()

@app.on_event("startup")
async def start_background_tasks():
    task = asyncio.create_task(periodic_cleanup())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)




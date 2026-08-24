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
from sheets import append_to_sheets


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
async def upload(files: List[UploadFile] = File(...)):
    results = []
    for file in files:
        data = await file.read()
        if file.filename.endswith('.pdf'):
            results.append(read_pdf_file(data,file.filename))
        else:
            results.append(read_image_file(data))

    results = validate_json_data(results)
    sorted_json = sort_json_datafile(results)
    append_to_sheets(sorted_json)
    return {"Processed" : len(sorted_json)}


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




def read_image_file(file_bytes):

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
                            "media_type": "image/jpeg",
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





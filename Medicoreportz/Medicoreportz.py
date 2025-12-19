import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

import os
import re
import json
import cv2
import numpy as np
import pdfplumber
from PIL import Image
from docx import Document
from langdetect import detect
LAB_REFERENCE = {
    "Hemoglobin": {"low": 12.0, "high": 16.0, "unit": "g/dL"},
    "WBC": {"low": 4.0, "high": 11.0, "unit": "x10^3/µL"},
    "Platelets": {"low": 150, "high": 450, "unit": "x10^3/µL"},
    "Glucose": {"low": 70, "high": 99, "unit": "mg/dL"}
}



def extract_text(file_path):
    file_path = os.path.normpath(file_path.strip().strip('"').strip("'"))

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    ext = file_path.lower().split('.')[-1]

    if ext == "txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if ext == "pdf":
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

    if ext == "docx":
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    if ext in ["png", "jpg", "jpeg"]:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image)

    raise ValueError("Unsupported file type")


def clean_text(text):
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\S+@\S+", "", text)
    text = re.sub(r"[^\w\s.,:/()%\-]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)

    text = text.replace("x10 3/L", "x10^3/µL")
    text = text.replace("x10 3 / L", "x10^3/µL")

    return text.strip()



def extract_patient_info(text):
    info = {"name": None, "age": None, "gender": None}
    name = re.search(r"Patient Name[:\-]?\s*([A-Za-z ]+?)(?:\s+Age|\n|$)", text, re.I)
    age = re.search(r"Age[:\-]?\s*(\d+)", text, re.I)
    gender = re.search(r"(Gender|Sex)[:\-]?\s*(Male|Female)", text, re.I)
    if name:
        info["name"] = name.group(1).strip()
    if age:
        info["age"] = int(age.group(1))
    if gender:
        info["gender"] = gender.group(2)

    return info


def extract_vital_signs(text):
    vitals = {}

    bp = re.search(r"Blood Pressure[:\-]?\s*(\d+/\d+\s*mmHg)", text, re.I)
    hr = re.search(r"Heart Rate[:\-]?\s*(\d+\s*bpm)", text, re.I)

    if bp:
        vitals["blood_pressure"] = bp.group(1)
    if hr:
        vitals["heart_rate"] = hr.group(1)

    return vitals


def extract_labs(text):
    labs = []

    CBC_TESTS = [
        "HEMOGLOBIN", "RBC", "PCV", "MCV", "MCH", "MCHC", "RDW",
        "WBC", "PLATELET"
    ]

    UNIT_MAP = {
        "g/dL": "g/dL",
        "fL": "fL",
        "pg": "pg",
        "%": "%",
        "cumm": "cumm",
        "mill/cumm": "mill/cumm",
        "cells/mcL": "cells/mcL"
    }

    for line in text.splitlines():
        line_clean = line.strip()

        for test in CBC_TESTS:
            if test in line_clean.upper():
                parts = line_clean.split()

                for p in parts:
                    try:
                        value = float(p)
                    except ValueError:
                        continue

                    unit = "Unknown"
                    for u in UNIT_MAP:
                        if u.lower() in line_clean.lower():
                            unit = u
                            break

                    labs.append({
                        "test_name": test.title(),
                        "value": value,
                        "unit": unit
                    })
                break

    return labs


def enrich_labs(labs):
    reference_ranges = {
        "glucose": {
            "range": (70, 99),
            "unit": "mg/dL"
        },
        "wbc": {
            "range": (4.0, 11.0),
            "unit": "x10^3/µL"
        },
        "hemoglobin": {
            "range": (13.0, 17.0),
            "unit": "g/dL"
        },
        "platelet": {
            "range": (150, 450),
            "unit": "x10^3/µL"
        },
        "cholesterol": {
            "range": (0, 200),
            "unit": "mg/dL"
        }
    }

    aliases = {
        "glucose": ["glucose", "blood glucose", "fasting glucose", "random glucose"],
        "wbc": ["wbc", "white blood cell", "white blood cells"],
        "hemoglobin": ["hemoglobin", "hb", "hgb"],
        "platelet": ["platelet", "platelets", "plt"],
        "cholesterol": ["cholesterol", "total cholesterol"]
    }

    enriched = []

    for lab in labs:
        name_raw = lab["test_name"].lower()
        value = lab["value"]
        unit = lab["unit"]

        canonical = None
        confidence = 0.6

        for key, alias_list in aliases.items():
            if any(a in name_raw for a in alias_list):
                canonical = key
                confidence = 0.95
                break

        if canonical and canonical in reference_ranges:
            low, high = reference_ranges[canonical]["range"]

            if value < low:
                status = "Low"
                highlight = "warning"
            elif value > high:
                status = "High"
                highlight = "warning"
            else:
                status = "Normal"
                highlight = "normal"

            normal_range = f"{low}–{high}"

        else:
            status = "Unknown"
            highlight = "unknown"
            normal_range = "Not available"
            confidence = 0.4

        enriched.append({
            "test_name": lab["test_name"],
            "value": value,
            "unit": unit,
            "normal_range": normal_range,
            "status": status,
            "highlight": highlight,
            "confidence": round(confidence, 2)
        })
    return enriched



def add_highlight_level(labs):
    for lab in labs:
        if lab["status"] == "Normal":
            lab["highlight"] = "normal"
        elif lab["status"] == "Low":
            lab["highlight"] = "warning"
        elif lab["status"] == "High":
            lab["highlight"] = "warning"
        else:
            lab["highlight"] = "unknown"
    return labs


def convert_to_json(text, filename):
    try:
        language = detect(text)
    except:
        language = "unknown"

    extracted_labs = extract_labs(text)
    enriched_labs = enrich_labs(extracted_labs)

    return {
        "file_name": os.path.basename(filename),
        "language": language,
        "patient": extract_patient_info(text),
        "vital_signs": extract_vital_signs(text),
        "labs": add_highlight_level(enriched_labs),
        "raw_text": text
    }



def format_labs_for_llm(labs):
    if not labs:
        return "No lab values were detected."

    return "\n".join(
        f"- {lab['test_name']}: {lab['value']} {lab['unit']} "
        f"(Normal: {lab['normal_range']}, Status: {lab['status']})"
        for lab in labs
    )
def build_summary_prompt(data):
    patient = data.get("patient", {})
    vitals = data.get("vital_signs", {})
    labs_text = format_labs_for_llm(data.get("labs", []))

    greeting = f"Hello {patient['name']}," if patient.get("name") else "Hello,"

    patient_context = []
    if patient.get("age"):
        patient_context.append(f"Age: {patient['age']}")
    if patient.get("gender"):
        patient_context.append(f"Gender: {patient['gender']}")

    vitals_context = []
    if vitals.get("blood_pressure"):
        vitals_context.append(f"Blood Pressure: {vitals['blood_pressure']}")
    if vitals.get("heart_rate"):
        vitals_context.append(f"Heart Rate: {vitals['heart_rate']}")
    if data.get("labs"):
        labs_text = format_labs_for_llm(data["labs"])
    else:
        labs_text = "Lab values were present but could not be fully interpreted."
    return f"""
{greeting}

You are a medical assistant summarizing a health report.

Rules:
- Write ONE summary paragraph
- Use simple, non-technical language
- Do NOT diagnose diseases
- Do NOT suggest treatments
- Be calm and reassuring
- Do NOT discuss about future tests and investigations
- Only express what is present in the report and do not express about future plans 
Patient Information:
{chr(10).join(patient_context) if patient_context else "Not specified"}

Vital Signs:
{chr(10).join(vitals_context) if vitals_context else "Not available"}

Lab Results:
{labs_text}

Provide a friendly patient summary.
"""
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_summary(data):
    prompt = build_summary_prompt(data)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You generate patient-friendly medical summaries."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=250
    )

    return response.choices[0].message.content
def print_labs_with_highlight(labs):
    for lab in labs:
        tag = ""
        if lab["highlight"] == "warning":
            tag = "[!]"
        elif lab["highlight"] == "normal":
            tag = "[OK]"

        print(
            f"{tag} {lab['test_name']}: {lab['value']} {lab['unit']} "
            f"(Normal: {lab['normal_range']}, Status: {lab['status']})"
        )


def process_file(file_path):
    file_path = file_path.strip().strip('"').strip("'")
    raw_text = extract_text(file_path)
    cleaned_text = clean_text(raw_text)
    data = convert_to_json(cleaned_text, file_path)

    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    summary = generate_summary(data)
    print("\n--- Patient Summary ---\n")
    print(summary)
    print("\n--- Lab Highlights ---\n")
    print_labs_with_highlight(data["labs"])
def analyze_file(file_path):
    raw_text = extract_text(file_path)
    cleaned_text = clean_text(raw_text)
    data = convert_to_json(cleaned_text, file_path)
    summary = generate_summary(data)
    return data, summary



if __name__ == "__main__":
    path = input("Enter file path: ")
    process_file(path)


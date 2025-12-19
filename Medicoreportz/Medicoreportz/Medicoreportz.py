import os
import re
import json
import pdfplumber
import pytesseract
from PIL import Image
from docx import Document
from langdetect import detect
LAB_REFERENCE = {
    "Hemoglobin": {"low": 12.0, "high": 16.0, "unit": "g/dL"},
    "WBC Count": {"low": 4.0, "high": 11.0, "unit": "x10^3/uL"},
    "Platelet Count": {"low": 150, "high": 450, "unit": "x10^3/uL"},
    "Glucose": {"low": 70, "high": 99, "unit": "mg/dL"}
}


def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()

    if ext in [".txt"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if ext in [".pdf"]:
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()

    if ext in [".png", ".jpg", ".jpeg"]:
        img = Image.open(file_path).convert("L")

        img = img.point(lambda x: 0 if x < 140 else 255, "1")

        custom_config = r"--oem 3 --psm 6"

        return pytesseract.image_to_string(
            img,
            config=custom_config
        ).strip()

    if ext in [".docx"]:
        doc = docx.Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    raise ValueError("Unsupported file type")

def normalize_text(text):
    text = text.replace("µ", "u")
    text = text.replace(",", ".")
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def clean_text(text):
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\S+@\S+", "", text)
    text = re.sub(r"[^a-zA-Z0-9.,:/()\n ]", " ", text)
    text = re.sub(r"\s+", " ", text)
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
LAB_PATTERNS = {
    "Hemoglobin": r"(hemoglobin|hb)[^\d]{0,40}([\d]+\.?\d*)",
    "PCV": r"(pcv|packed cell volume)[^\d]{0,40}([\d]+\.?\d*)",
    "RBC Count": r"(rbc)[^\d]{0,40}([\d]+\.?\d*)",
    "WBC Count": r"(wbc)[^\d]{0,40}([\d]+\.?\d*)",
    "Platelet Count": r"(platelet)[^\d]{0,40}([\d]+)",
    "Glucose": r"(glucose)[^\d]{0,40}([\d]+\.?\d*)",
}

def extract_labs(text):
    labs = []

    for name, pattern in LAB_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            labs.append({
                "test_name": name,
                "value": float(match.group(2))
            })

    return labs

def enrich_labs(extracted_labs):
    enriched = []

    for lab in extracted_labs:
        name = lab.get("test_name")
        value = lab.get("value")

        if name not in LAB_REFERENCE or value is None:
            continue

        ref = LAB_REFERENCE[name]

        if value < ref["low"]:
            status = "Low"
            highlight = "warning"
        elif value > ref["high"]:
            status = "High"
            highlight = "warning"
        else:
            status = "Normal"
            highlight = "normal"

        enriched.append({
            "test_name": name,
            "value": value,
            "unit": ref["unit"],
            "normal_range": f"{ref['low']}–{ref['high']}",
            "status": status,
            "highlight": highlight
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
    enriched_labs = add_highlight_level(enriched_labs)

    return {
        "file_name": os.path.basename(filename),
        "language": language,
        "patient": extract_patient_info(text),
        "vital_signs": extract_vital_signs(text),
        "labs": enriched_labs,
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
    labs = data.get("labs", [])

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

    labs_text = format_labs_for_llm(labs)

    return f"""
{greeting}

You are a medical assistant summarizing a health report.

Rules:
- Write ONE short summary paragraph
- Use simple, non-technical language
- Do NOT diagnose diseases
- Do NOT suggest treatments
- Be calm and reassuring
- Only describe what is present in the report

Patient Information:
{chr(10).join(patient_context) if patient_context else "Not specified"}

Vital Signs:
{chr(10).join(vitals_context) if vitals_context else "Not available"}

Lab Results:
{labs_text}

Provide a friendly patient summary.
"""

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
def generate_summary(data):
    prompt = build_summary_prompt(data)

    from groq import Groq
    import os

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=200
    )

    return response.choices[0].message.content.strip()



def process_file(file_path):
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


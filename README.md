# Medicoreportz
MedicoReportz

MedicoReportz is an AI-assisted medical report analysis tool that extracts, structures, and explains laboratory results from medical reports such as PDFs, images, and text files. The system is designed to handle real-world lab report formats, especially structured reports like Complete Blood Count (CBC), and present results in a clear, verifiable, and user-friendly way.

Features

Upload medical reports in PDF, PNG, JPG, JPEG, or TXT format

OCR-based text extraction optimized for table-heavy lab reports

Structured extraction of laboratory values

Automatic comparison against reference ranges

Clear flagging of abnormal results (Low / High / Normal)

AI-generated patient-friendly summaries based only on extracted data

Editable extracted data with summary re-generation

Clean, dark-mode Streamlit interface with animations

How It Works

Upload Report
Users upload a medical report through the web interface.

OCR & Text Processing
Image and PDF reports are processed using Tesseract OCR with OpenCV-based preprocessing to preserve table structure.

Lab Extraction
A custom, stateful parser reconstructs lab values from fragmented OCR output.

Data Enrichment
Extracted lab values are normalized, mapped to reference ranges, and flagged if abnormal.

Summary Generation
An AI model generates a readable explanation strictly based on the extracted values.

Review & Edit
Users can view and edit extracted technical data and regenerate the summary if corrections are needed.

Tech Stack

Frontend: Streamlit

OCR: Tesseract OCR

Image Processing: OpenCV, PIL

PDF Processing: pdf2image

Backend: Python

AI Integration: LLM-based summarization (Groq API supported)


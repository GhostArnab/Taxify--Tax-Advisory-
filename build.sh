#!/usr/bin/env bash
# exit on error
set -o errexit

# Install system dependencies for Tesseract OCR and PDF-to-image conversion
apt-get update && apt-get install -y tesseract-ocr poppler-utils

# Install Python dependencies from requirements.txt
pip install -r requirements.txt
<div align="center">
  
  # ⚡ TaxiFy 
  
  **AI-Powered Tax Planning & Advisory for Indian Salaried Employees**

  [![Python](https://img.shields.io/badge/Python-3.13+-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
  [![Flask](https://img.shields.io/badge/Flask-3.0+-black.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
  [![Gemini AI](https://img.shields.io/badge/Google%20Gemini-AI-orange.svg?logo=google&logoColor=white)](https://aistudio.google.com/)
  [![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E.svg?logo=supabase&logoColor=white)](https://supabase.com/)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
  [![Deployed on Render](https://img.shields.io/badge/Deployed_on-Render-black?logo=render)](https://taxify-tax-advisory.onrender.com)

  [Live Demo](https://taxify-tax-advisory.onrender.com) • [Report Bug](#) • [Request Feature](#)

</div>

---

## 📖 Overview

**TaxiFy** (formerly TaxWala) is an intelligent, automated web application designed to simplify income tax calculations for Indian salaried individuals. By leveraging OCR and Google's powerful Gemini 2.5 AI, TaxiFy automatically extracts financial data from uploaded salary slips (or Form 16) and provides a side-by-side comparison of the **Old vs. New Tax Regimes (Updated for FY 2025-26)**.

But it doesn't stop there—TaxiFy features a built-in AI Tax Advisor that chats with you to provide personalized investment and tax-saving strategies based on your unique financial profile.

## ✨ Key Features

- **📄 Smart Document Extraction:** Upload a PDF or Image of your salary slip and watch the AI instantly extract Gross Salary, HRA, Basic Salary, Deductions, and more.
- **⚖️ Regime Comparison:** Side-by-side breakdown of your tax liability under both the Old and New tax regimes (fully updated for the FY 2025-26 budget).
- **💡 Smart Recommendations:** Automatically highlights which regime saves you the most money.
- **🤖 AI Tax Advisor:** An interactive chat interface where an AI Chartered Accountant gives you tailored advice on section 80C, 80D, HRA, and NPS investments to maximize your savings.
- **🎨 Premium UI:** A stunning, fully responsive dark glassmorphic interface with micro-animations.
- **🔒 Secure Architecture:** Stateless file processing and secure PostgreSQL conversational logging.

## 🛠️ Tech Stack

- **Backend:** Python, Flask, Gunicorn
- **AI Integration:** Google Gemini API (gemini-2.5-flash)
- **Database:** PostgreSQL (Supabase) for session and conversation state management
- **Frontend:** HTML5, CSS3 (Vanilla Glassmorphic Design System), JavaScript
- **Document Processing:** PyPDF2, pdf2image, PyTesseract (OCR)
- **Deployment:** Render (PaaS)

## 🚀 Live Demo
Check out the live application here: **[TaxiFy Live](https://taxify-tax-advisory.onrender.com)**

---

## 💻 Local Setup & Installation

If you want to run TaxiFy on your local machine, follow these steps:

### Prerequisites
- Python 3.10+
- Tesseract-OCR installed on your system
- A free Supabase Project (PostgreSQL)
- A free Google Gemini API Key

### 1. Clone the repository
```bash
git clone https://github.com/GhostArnab/Taxify--Tax-Advisory-.git
cd Taxify--Tax-Advisory-
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Rename the `Sample.env` file to `.env` and add your secure keys:
```env
DB_URL="postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres"
GEMINI_API_KEY="your_gemini_api_key_here"
FLASK_SECRET_KEY="a_random_secure_string_here"
FLASK_DEBUG="true"
```

### 4. Initialize Database
Run the schema creation script to set up the necessary tables in Supabase:
```bash
python supabase_db_create.py
```

### 5. Run the Application
```bash
python app.py
```
*The app will be available at http://127.0.0.1:5000*

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

---
<div align="center">
  <i>Built with ❤️ by <a href="https://github.com/GhostArnab">Arnab</a></i>
</div>

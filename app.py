import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import PyPDF2
import requests
import json
from tax_calculator import calculate_tax_old, calculate_tax_new
import psycopg2
from datetime import datetime
from decimal import Decimal
import markdown2

# Override default print to prevent UnicodeEncodeError on Windows terminals
_original_print = print
def safe_print(*args, **kwargs):
    encoding = sys.stdout.encoding or 'utf-8'
    safe_args = []
    for arg in args:
        if isinstance(arg, str):
            # Encode to the target console encoding and replace unsupported characters
            safe_args.append(arg.encode(encoding, errors='replace').decode(encoding))
        else:
            safe_args.append(arg)
    _original_print(*safe_args, **kwargs)

print = safe_print

load_dotenv()

app = Flask(__name__, template_folder='templates')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-fallback-secret-key-change-in-production')

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# Helper to check allowed file
def allowed_file(filename):
    allowed_ext = {'pdf', 'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_ext

def extract_text_from_file(filepath):
    ext = filepath.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        # Try text extraction from PDF
        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = " ".join(page.extract_text() or '' for page in reader.pages)
            if text.strip():
                return text
        except Exception:
            pass
        # If text extraction fails, use OCR
        images = convert_from_path(filepath)
        text = ''
        for img in images:
            text += pytesseract.image_to_string(img)
        return text
    elif ext in {'png', 'jpg', 'jpeg'}:
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img)
        return text
    return ''

def call_gemini_api(prompt):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print('[ERROR] GEMINI_API_KEY is missing from environment!')
        return None
    url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=' + api_key
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        try:
            result = response.json()
            # Gemini 2.5 Flash may return multiple parts (thinking + answer).
            # The actual answer is the last text part that is NOT a thought.
            parts = result['candidates'][0]['content']['parts']
            answer = None
            for part in parts:
                if part.get('thought'):
                    continue  # Skip thinking parts
                if 'text' in part:
                    answer = part['text']
            # Fallback: if no non-thought part found, use the last part with text
            if answer is None:
                for part in reversed(parts):
                    if 'text' in part:
                        answer = part['text']
                        break
            print(f'[DEBUG] Gemini raw answer (first 500 chars): {answer[:500] if answer else "None"}')
            return answer
        except Exception as e:
            print('[ERROR] Could not parse Gemini response:', e)
            print('[DEBUG] Full response JSON:', response.text[:1000])
            return None
    else:
        print(f'[ERROR] Gemini API call failed. Status: {response.status_code}, Response: {response.text}')
        return None

def build_gemini_prompt(raw_text):
    return (
        "You are an expert Indian payroll analyst. Extract financial data from the salary slip text below.\n\n"
        "RULES:\n"
        "1. If the slip is for a single month, ANNUALIZE all values (multiply by 12).\n"
        "2. Return ONLY a valid JSON object — no markdown, no explanation.\n"
        "3. If a value is not found, set it to 0.\n\n"
        "FIELD MAPPING — use these rules to map salary slip line items:\n"
        "- gross_salary: Total earnings / Gross Salary / Total Pay (sum of all earning components).\n"
        "- basic_salary: Basic Pay / Basic Salary.\n"
        "- hra_received: House Rent Allowance / HRA.\n"
        "- rent_paid: House Rent / Rent Paid / Rent Deduction / HRA deduction from employee side. "
        "Look for any rent-related deduction or declared rent amount. If the slip shows an 'HRA exemption' or 'Rent Paid' field, use that value.\n"
        "- deduction_80c: Section 80C deductions — EPF / PF (Provident Fund) employee contribution, PPF, ELSS, LIC, NSC, or any line item mentioning 80C. "
        "If only PF/EPF employee contribution is shown, use that.\n"
        "- deduction_80d: Section 80D / Medical Insurance Premium / Health Insurance / Mediclaim. "
        "Also look for 'Medical Allowance', 'Medical Reimbursement', or any medical-related benefit or deduction.\n"
        "- standard_deduction: Standard Deduction (Rs. 75,000 for FY 2024-25 / AY 2025-26 under new regime, Rs. 50,000 under old regime). If not explicitly stated, set to 0.\n"
        "- professional_tax: Professional Tax / PT / Employment Tax.\n"
        "- tds: TDS / Tax Deducted at Source / Income Tax / IT deduction.\n\n"
        "JSON keys: gross_salary, basic_salary, hra_received, rent_paid, deduction_80c, deduction_80d, standard_deduction, professional_tax, tds\n\n"
        f"Salary Slip Text:\n{raw_text}\n\nJSON:"
    )

def clean_gemini_json_response(response_text):
    """Extract a JSON object from Gemini's response, handling thinking text,
    markdown code blocks, and other surrounding content."""
    import re
    if not response_text:
        return ''
    text = response_text.strip()

    # Strategy 1: Find JSON inside a ```json ... ``` code block
    match = re.search(r'```json\s*\n?(.*?)\n?\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Strategy 2: Find JSON inside any ``` ... ``` code block
    match = re.search(r'```\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        if candidate.startswith('{'):
            return candidate

    # Strategy 3: Find a bare JSON object { ... } anywhere in the text
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if match:
        return match.group(0).strip()

    # Fallback: strip backticks from edges
    cleaned = text
    if cleaned.startswith('```'):
        cleaned = cleaned.lstrip('`')
        if cleaned.lower().startswith('json'):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    if cleaned.endswith('```'):
        cleaned = cleaned.rstrip('`').strip()
    return cleaned

# Helper to load/save conversation log

def load_conversation(session_id):
    db_url = os.getenv('DB_URL')
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute('SELECT role, content, timestamp FROM ConversationLog WHERE session_id=%s ORDER BY created_at ASC', (session_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [{'role': r[0], 'content': r[1], 'timestamp': r[2].isoformat() if r[2] else ''} for r in rows]
    except Exception as e:
        print('[ERROR] Could not load conversation from DB:', e)
        return []

def save_conversation_turn(session_id, role, content):
    db_url = os.getenv('DB_URL')
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute('INSERT INTO ConversationLog (session_id, role, content, timestamp) VALUES (%s, %s, %s, %s)',
            (session_id, role, content, datetime.now()))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print('[ERROR] Could not save conversation turn to DB:', e)

def convert_decimals(obj):
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj

# Gemini advisor prompt builder

def build_advisor_prompt(user_data, tax_old, tax_new, selected_regime, convo):
    history = ''
    for turn in convo:
        if turn['role'] == 'user':
            history += f"User: {turn['content']}\n"
        else:
            history += f"Advisor: {turn['content']}\n"
    user_data_clean = convert_decimals(user_data)
    prompt = f"""
You are a thoughtful, step-by-step tax advisor for Indian salaried individuals. Your goal is to help the user optimize their taxes and investments. Think step by step, ask clarifying questions if needed, and always step back to consider the bigger goal of maximizing tax savings and financial well-being.

Here is the user's financial data and tax results:
{json.dumps(user_data_clean, indent=2)}
Old Regime Tax: Rs.{tax_old}
New Regime Tax: Rs.{tax_new}
User Selected Regime: {selected_regime}

Conversation so far:
{history}

If you need more information, ask a smart, contextual follow-up question. If you have enough information, provide a clear, actionable, personalized tax-saving and investment advice. Always explain your reasoning. Only ask one question at a time. If you are giving advice, do not ask further questions.

**When giving advice, format your response using Markdown for headings, bold, and lists.**
"""
    return prompt

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            session_id = str(uuid.uuid4())
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id + '_' + filename)
            file.save(save_path)
            return redirect(url_for('extract', session_id=session_id, filename=filename))
    return render_template('upload.html')

@app.route('/extract')
def extract():
    session_id = request.args.get('session_id')
    filename = request.args.get('filename')
    if not session_id or not filename:
        flash('Invalid session or file.')
        return redirect(url_for('upload'))
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], session_id + '_' + filename)
    raw_text = extract_text_from_file(filepath)
    print('\n[DEBUG] Extracted Text:\n', raw_text)
    prompt = build_gemini_prompt(raw_text)
    print('\n[DEBUG] Gemini Prompt:\n', prompt)
    gemini_response = call_gemini_api(prompt)
    print('\n[DEBUG] Gemini Response:\n', gemini_response)
    try:
        cleaned_response = clean_gemini_json_response(gemini_response)
        extracted_data = json.loads(cleaned_response)
    except Exception as e:
        print('[ERROR] Could not parse cleaned Gemini response:', e)
        extracted_data = {
            'gross_salary': 0,
            'basic_salary': 0,
            'hra_received': 0,
            'rent_paid': 0,
            'deduction_80c': 0,
            'deduction_80d': 0,
            'standard_deduction': 0,
            'professional_tax': 0,
            'tds': 0
        }
    return render_template('form.html', data=extracted_data, session_id=session_id, filename=filename)

@app.route('/calculate', methods=['POST'])
def calculate():
    data = {
        'session_id': request.form.get('session_id'),
        'gross_salary': request.form.get('gross_salary', 0),
        'basic_salary': request.form.get('basic_salary', 0),
        'hra_received': request.form.get('hra_received', 0),
        'rent_paid': request.form.get('rent_paid', 0),
        'deduction_80c': request.form.get('deduction_80c', 0),
        'deduction_80d': request.form.get('deduction_80d', 0),
        'standard_deduction': request.form.get('standard_deduction', 0),
        'professional_tax': request.form.get('professional_tax', 0),
        'tds': request.form.get('tds', 0)
    }
    selected_regime = request.form.get('regime', 'new')
    session_id = data['session_id']
    # Calculate taxes
    tax_old = calculate_tax_old(data)
    tax_new = calculate_tax_new(data)
    best_regime = 'old' if tax_old < tax_new else 'new'
    # Save to Supabase
    db_url = os.getenv('DB_URL')
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        # Insert or update UserFinancials
        cur.execute('''INSERT INTO UserFinancials (session_id, gross_salary, basic_salary, hra_received, rent_paid, deduction_80c, deduction_80d, standard_deduction, professional_tax, tds) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (session_id) DO UPDATE SET gross_salary=EXCLUDED.gross_salary, basic_salary=EXCLUDED.basic_salary, hra_received=EXCLUDED.hra_received, rent_paid=EXCLUDED.rent_paid, deduction_80c=EXCLUDED.deduction_80c, deduction_80d=EXCLUDED.deduction_80d, standard_deduction=EXCLUDED.standard_deduction, professional_tax=EXCLUDED.professional_tax, tds=EXCLUDED.tds''',
            (session_id, data['gross_salary'], data['basic_salary'], data['hra_received'], data['rent_paid'], data['deduction_80c'], data['deduction_80d'], data['standard_deduction'], data['professional_tax'], data['tds']))
        # Insert or update TaxComparison
        cur.execute('''INSERT INTO TaxComparison (session_id, tax_old_regime, tax_new_regime, best_regime, selected_regime) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (session_id) DO UPDATE SET tax_old_regime=EXCLUDED.tax_old_regime, tax_new_regime=EXCLUDED.tax_new_regime, best_regime=EXCLUDED.best_regime, selected_regime=EXCLUDED.selected_regime''',
            (session_id, tax_old, tax_new, best_regime, selected_regime))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print('[ERROR] Could not save to Supabase:', e)
    return render_template('results.html', tax_old=tax_old, tax_new=tax_new, best_regime=best_regime, selected_regime=selected_regime, data=data)

@app.route('/advisor', methods=['GET', 'POST'])
def advisor():
    session_id = request.args.get('session_id') or request.form.get('session_id')
    if not session_id:
        flash('Session missing.')
        return redirect(url_for('index'))
    # Load user data and tax results from DB
    db_url = os.getenv('DB_URL')
    user_data = {}
    tax_old = tax_new = 0
    selected_regime = 'new'
    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute('SELECT gross_salary, basic_salary, hra_received, rent_paid, deduction_80c, deduction_80d, standard_deduction, professional_tax, tds FROM UserFinancials WHERE session_id=%s', (session_id,))
        row = cur.fetchone()
        if row:
            user_data = {
                'gross_salary': row[0],
                'basic_salary': row[1],
                'hra_received': row[2],
                'rent_paid': row[3],
                'deduction_80c': row[4],
                'deduction_80d': row[5],
                'standard_deduction': row[6],
                'professional_tax': row[7],
                'tds': row[8]
            }
        cur.execute('SELECT tax_old_regime, tax_new_regime, selected_regime FROM TaxComparison WHERE session_id=%s', (session_id,))
        row = cur.fetchone()
        if row:
            tax_old, tax_new, selected_regime = row
        cur.close()
        conn.close()
    except Exception as e:
        print('[ERROR] Could not load user/tax data for advisor:', e)
    # Load conversation history
    convo = load_conversation(session_id)
    if request.method == 'POST':
        user_msg = request.form.get('user_message', '').strip()
        if user_msg:
            convo.append({'role': 'user', 'content': user_msg, 'timestamp': datetime.now().isoformat()})
            save_conversation_turn(session_id, 'user', user_msg)
    # Build prompt and get Gemini's response
    prompt = build_advisor_prompt(user_data, tax_old, tax_new, selected_regime, convo)
    gemini_response = call_gemini_api(prompt)
    print('\n[DEBUG] Advisor Gemini Response:\n', gemini_response)
    # Clean and add Gemini's response to convo
    if gemini_response:
        cleaned = clean_gemini_json_response(gemini_response) if gemini_response.strip().startswith('```') else gemini_response.strip()
        convo.append({'role': 'advisor', 'content': cleaned, 'timestamp': datetime.now().isoformat()})
        save_conversation_turn(session_id, 'advisor', cleaned)
    # Find last advisor message
    last_advisor = next((turn['content'] for turn in reversed(convo) if turn['role'] == 'advisor'), '')
    advisor_message_html = markdown2.markdown(last_advisor) if last_advisor else ''
    # Render markdown for all conversation turns
    convo_rendered = []
    for turn in convo:
        rendered_content = markdown2.markdown(turn['content']) if turn['content'] else ''
        convo_rendered.append({'role': turn['role'], 'content_html': rendered_content})
    return render_template('ask.html', advisor_message_html=advisor_message_html, session_id=session_id, conversation=convo_rendered)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
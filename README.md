# ScrutinyAI — Pre-filing Scrutiny Checker

**ScrutinyAI** is a comprehensive, intelligent pre-filing scrutiny checker designed specifically for Karnataka High Court advocates. It ingests civil draft PDFs and evaluates them against a strict 21-point structural, formatting, and fiscal checklist—helping legal professionals identify objections before the registry does.

## 🚀 Features

- **Intelligent Filing Analysis:** Runs checks across three vectors—Format Geometry (margins, line limits), Document Structure (sequence, required sections, signatures), and Fiscal (Court fee formulas and plausibility).
- **Hybrid OCR Pipeline:** Gracefully handles both natively exported PDFs (via PyMuPDF) and scanned physical filings (via Tesseract).
- **Secured Gemini 2.0 Integration:** Utilizes Google Gemini's context-windowing for complex language tasks (e.g., verifying if specific grounds exist within a nested summary), parsing the outputs deterministically into structured objection objects.
- **Interactive UI Dashboard:** A premium, real-time dashboard built in Next.js. Features live check progress steppers, drag-and-drop file chunking, and clipboard-copying for easy summarization reporting.
- **Background Task Processing:** Scalable, non-blocking Python backend powered by FastAPI's asyncio queue mechanism that runs documents in the background without tying up server response times.

---

## 🏗 Technology Stack

- **Frontend:** Next.js 14, React, TailwindCSS, TypeScript
- **Backend Analytics Engine:** Python 3.10+, FastAPI
- **Database & Authentication:** Supabase (PostgreSQL)
- **Document Processing:** PyMuPDF (`fitz`), Tesseract OCR
- **AI Core:** Google Gemini (`google-genai`)
- **Queue/Cache:** Upstash Redis

---

## 📁 Repository Structure

```text
scrutinyai/
├── backend/
│   ├── api/             # FastAPI routers, startup hooks, entrypoints
│   ├── ocr/             # PyMuPDF and Tesseract logic, geometry detection
│   ├── rule_engine/     # 21-point rule validation heuristics and Gemini bridges
│   └── worker/          # Background worker tasks for the extraction pipeline
├── frontend/
│   ├── app/             # Next.js 14 App Router (Auth guards, report/dashboard views)
│   ├── components/      # UI primitives (Nav, Overhauls, Upload Zones, Badges)
│   ├── lib/             # API layer, Supabase clients
│   └── types/           # Shared TS typings 
├── rules/               # JSON Schema models of required checklist metrics
└── requirements.txt     # Python backend dependencies
```

---

## 🛠 Local Setup & Development

### 1. Prerequisites
- **Node.js 18+** & `npm`
- **Python 3.10+** (Recommend using a virtual environment)
- **Tesseract OCR** (Needs to be installed on your OS environment)

### 2. Environment Variables

Create two separate `.env` files for both applications.

#### Backend (`.env` in root)
```bash
SUPABASE_URL=YOUR_SUPABASE_PROJECT_URL
SUPABASE_SERVICE_KEY=YOUR_SUPABASE_SERVICE_ROLE_KEY
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
MAX_UPLOAD_SIZE_MB=100
```

#### Frontend (`frontend/.env.local`)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=YOUR_SUPABASE_PROJECT_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY
```

### 3. Run the Backend (FastAPI)

1. Navigate to the root folder: `cd scrutinyai/`
2. Install python packages: `pip install -r requirements.txt`
3. Make sure the python path is mounted (Windows): `set PYTHONPATH=D:\ScrutinyAI\scrutinyai`
4. Boot the Uvicorn server: 
```bash
python -m uvicorn backend.api.main:app --reload --port 8000
```
*(Optionally tag `--log-level debug` to inspect the OCR pipelines actively).*

### 4. Run the Frontend (Next.js)

1. Open a new terminal and navigate to the frontend: `cd scrutinyai/frontend/`
2. Install packages: `npm install`
3. Start the dev server:
```bash
npm run dev
```

### 5. Start Using!
Open your browser to `http://localhost:3000`. Create an account on the register page safely handled by Supabase Auth, and drop a Civil document into the portal!

---

## 🔐 Licensing & Compliance
Because Karnataka High Court documents can involve PII context, this stack utilizes Google Gemini with standard zero-retention policies in tandem with secured storage via Supabase. User documents stay compartmentalized and localized.

# EventDhara AI Data Operations Platform

An enterprise-grade, production-oriented AI Data Operations Platform built from scratch to manage large collections of event decoration photographs, perform automated image quality verification, detect visual and exact duplicates, classify decoration setups using Google Gemini Vision AI, generate structured catalog metadata, and synchronize approved assets to Google Drive.

---

## 1. System Architecture

```
                                    +-----------------------------+
                                    |    React 19 + TypeScript    |
                                    | Vite • Tailwind • shadcn/ui |
                                    +--------------+--------------+
                                                   | HTTP / REST (Port 3000 -> 8000)
                                                   v
                                    +-----------------------------+
                                    |    FastAPI Backend Engine   |
                                    | Pydantic v2 • Repository DL |
                                    +--------------+--------------+
                                                   |
           +--------------------+------------------+-------------------+--------------------+
           |                    |                                      |                    |
           v                    v                                      v                    v
+--------------------+ +--------------------+                +--------------------+ +--------------------+
|   PostgreSQL 18    | |  OpenCV & Pillow   |                |  Google Gemini AI  | |  Google Drive Sync |
| SQLAlchemy Models  | | ImageHash (pHash)  |                | Official GenAI SDK | | Hierarchical Cloud |
| 30 Seed Categories | | Laplacian Variance |                | Structured Output  | | Verified Transfer  |
+--------------------+ +--------------------+                +--------------------+ +--------------------+
```

---

## 2. Technology Stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Lucide React, React Router v7, TanStack Query v5, Recharts.
- **Backend:** Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Psycopg2.
- **Database:** PostgreSQL 18 (with connection pooling and automatic fallback resilience).
- **Image Processing & Vision:** OpenCV (Laplacian variance blur scoring), Pillow (integrity verification), ImageHash (perceptual pHash hamming distance), NumPy.
- **AI & Structured Vision:** Google Gemini API via official `google-genai` SDK with structured JSON enforcement.
- **Cloud & Export:** Google Drive API folder hierarchy simulation, Pandas, OpenPyXL (Excel & CSV exports).
- **Testing:** Pytest (API, Category hierarchy, Quality detection, Hashes), Vitest / TypeScript validation.

---

## 3. Monorepo Project Structure

```
eventdhara-ai/
│
├── frontend/
│   ├── src/
│   │   ├── components/ui/       # Enterprise Reusable UI (Buttons, Badges, Modals, Cards)
│   │   ├── layouts/             # Dark navy enterprise sidebar, Top navigation with breadcrumbs
│   │   ├── features/
│   │   │   ├── dashboard/       # Real-time PostgreSQL telemetry, volume charts, performance metrics
│   │   │   ├── categories/      # Unlimited-depth split-panel hierarchical category tree
│   │   │   ├── uploads/         # Streaming ZIP extraction & multi-file drag-and-drop
│   │   │   ├── processing/      # Ingestion pipeline queue & re-execution trigger
│   │   │   ├── galleries/       # Approved, Review Queue, and Rejected Galleries
│   │   │   ├── duplicates/      # Side-by-side comparison & non-destructive resolution
│   │   │   ├── metadata/        # AI Copywriting Studio with strictly visible decoration details
│   │   │   ├── google-drive/    # Automated cloud sync into canonical directory structure
│   │   │   ├── analytics/       # Deep-dive distribution telemetry and quality charts
│   │   │   ├── reports/         # Standardized Excel (.xlsx) and CSV exports
│   │   │   └── settings/        # Configurable runtime thresholds (blur, pHash, AI confidence)
│   │   ├── services/api.ts      # Typed Axios API client
│   │   ├── types/index.ts       # TypeScript enterprise data contracts
│   │   └── lib/utils.ts         # Formatting & styling utilities
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── backend/
│   ├── app/
│   │   ├── api/v1/              # RESTful API endpoints (Dashboard, Categories, Uploads, Images...)
│   │   ├── core/                # Configuration settings, PostgreSQL engine, CORS
│   │   ├── models/              # SQLAlchemy models (Category, ImageItem, UploadBatch, Metadata, AuditLog)
│   │   ├── schemas/             # Pydantic validation contracts
│   │   ├── repositories/        # Repository pattern for database abstraction
│   │   ├── services/            # Pipeline engine, Gemini AI, pHash duplicates, Drive sync, Exports
│   │   └── main.py              # FastAPI startup & lifecycle
│   ├── tests/                   # Pytest suite (API, Category CRUD, Image hashes, Blur detection)
│   ├── requirements.txt
│   └── .env
│
├── storage/
│   ├── uploads/                 # Temporary chunked upload cache
│   ├── extracted/               # Streaming ZIP extraction workspace
│   ├── processed/               # Canonical image storage (indexed by UUID)
│   ├── approved/                # Google Drive mirror directory hierarchy
│   ├── rejected/                # Preserved rejected images
│   ├── duplicates/              # Preserved duplicate images
│   └── exports/                 # Generated Excel & CSV reports
│
├── scripts/
│   └── seed_demo_data.py        # Generates test decoration photos & validates the full pipeline
├── .env.example
├── .gitignore
└── README.md
```

---

## 4. Quick Start & Run Commands

### Prerequisites
- Python 3.10+
- Node.js v20+ / v24+ & npm
- PostgreSQL 18 running locally or on network (database: `eventdhara_db`)

### Step 1: Database Setup
Make sure PostgreSQL is running and create the `eventdhara_db` database:
```powershell
# Using psql
psql -U postgres -h 127.0.0.1 -c "CREATE DATABASE eventdhara_db;"
```

### Step 2: Backend Setup & Startup
```powershell
cd C:\Users\HARSH\eventdhara-ai\backend

# Install dependencies
pip install -r requirements.txt

# Run Unit Tests
python -m pytest tests -v

# Start FastAPI server (Port 8000)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*The backend automatically initializes tables in PostgreSQL and seeds all 30 canonical categories on initial startup.*

### Step 3: Frontend Setup & Startup
```powershell
cd C:\Users\HARSH\eventdhara-ai\frontend

# Install dependencies
npm install

# Build production bundle
npm run build

# Start development server (Port 3000)
npm run dev -- --host 127.0.0.1 --port 3000
```
Open your browser at `http://localhost:3000`.

### Step 4: Seed Sample Demonstration Data (Optional)
To immediately populate the platform with verified demonstration photographs and test the full 5-step pipeline end-to-end:
```powershell
cd C:\Users\HARSH\eventdhara-ai
python scripts/seed_demo_data.py
```

---

## 5. Ingestion Pipeline Details (5 Steps)

1. **Step 1: File Validation & Integrity**
   - Verifies formats (JPEG, PNG, WEBP).
   - Validates dimensions (minimum 800x600 px required).
   - Inspects byte-level integrity to detect corrupt files.
   - Enforces min/max file size boundaries.

2. **Step 2: Global Duplicate Detection**
   - **SHA256:** Bit-for-bit cryptographic checksum match.
   - **pHash (Perceptual Hash):** Computes 64-bit DCT hash and tests Hamming distance across all current and historical records.
   - Preserves original files; flags candidate duplicates for side-by-side comparison.

3. **Step 3: Automated Quality & Blur Detection**
   - Employs OpenCV Laplacian variance filter (`cv2.Laplacian(img, cv2.CV_64F).var()`).
   - Images scoring below configurable threshold (default `100.0`) are flagged as blurry and diverted from auto-approval.

4. **Step 4: Gemini AI Vision Classification**
   - Calls Google Gemini Vision using the official Google Gen AI SDK.
   - Maps photographs into the canonical taxonomy (Birthday Decoration, Baby Shower, Anniversary, Welcome Baby, and 26 subcategories).
   - Extracts structured visual evidence and assigns confidence scores.

5. **Step 5: Final Policy Decision**
   - `APPROVED`: High-confidence classification (>= 0.75), passed quality, non-duplicate.
   - `REJECTED`: Severe blur, corrupt file, or clearly non-decoration photo.
   - `REVIEW_REQUIRED`: Low confidence, ambiguous decoration theme, edge-case sharpness, or API fallback.
   - `DUPLICATE`: Matches existing image by SHA256 or pHash Hamming distance <= 5.

---

## 6. Enterprise Safety & Security Standards

- **Anti-ZipSlip Protection:** Streaming ZIP extraction verifies destination paths to prevent directory traversal.
- **Memory Safety:** Streaming uploads and ZIP decompressions never load full archives into RAM.
- **Zero Data Loss:** Manual gallery actions and duplicate flags never delete source files.
- **Duplicate Verification on Approval:** Manual operator approval re-runs global duplicate verification before granting approval.
- **Audit Trails:** Operator actions, reviews, and status changes are recorded in the `audit_logs` table.
- **Strict Copywriting Guardrails:** Metadata generation only reflects visible decoration props; never hallucinates prices, guarantees, or stock.

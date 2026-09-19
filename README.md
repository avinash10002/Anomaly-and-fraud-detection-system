# 🛡️ MPLADS Anomaly & Fraud Detection System

> **An AI-powered audit and fund monitoring platform for the Members of Parliament Local Area Development Scheme (MPLADS)**, designed to detect financial overbilling, duplicated sanctions, vendor monopolization, and structural physical defects using Machine Learning, Computer Vision, and Rule-Based Data Analytics.

---

## 📌 Table of Contents

1. [Overview](#-overview)
2. [Key Capabilities](#-key-capabilities)
3. [System Architecture](#-system-architecture)
4. [Microservices Breakdown](#-microservices-breakdown)
5. [Detection Engines](#-detection-engines)
   - [Financial Anomaly Engine](#1-financial-anomaly-engine)
   - [NLP Work Similarity Engine](#2-nlp-work-similarity-engine)
   - [Computer Vision Image Engine](#3-computer-vision-image-engine)
   - [Graph & Vendor Collision Service](#4-graph--vendor-collision-service)
6. [Role-Based Access Control (RBAC)](#-role-based-access-control-rbac)
7. [Database Schema & Data Pipeline](#-database-schema--data-pipeline)
8. [Getting Started & Installation](#-getting-started--installation)
   - [Option A: Full Stack with Docker Compose](#option-a-full-stack-with-docker-compose-recommended)
   - [Option B: Running Locally (Development Mode)](#option-b-running-locally-development-mode)
9. [Environment Variables](#-environment-variables)
10. [API Specification](#-api-specification)
11. [Project Directory Structure](#-project-directory-structure)

---

## 📖 Overview

The **Members of Parliament Local Area Development Scheme (MPLADS)** enables Members of Parliament (MPs) to recommend developmental works in their constituencies with an emphasis on creating durable community assets (roads, drinking water facilities, schools, public health centers). 

Historically, monitoring over 60,000+ works across 400+ constituencies has suffered from:
- **Financial Outliers & Overbilling**: Disproportionate fund allocations for basic civil works exceeding state median benchmarks by dozens or hundreds of times.
- **Duplicate Sanctions & Ghost Works**: Boilerplate copy-pasted work descriptions sanctioned multiple times within the same block or village.
- **Physical Quality & Early Failure**: Completed works deteriorating prematurely (e.g. severe potholes within 8 months of completion) despite full fund disbursement.
- **Lack of Verification Feedback**: Inability for citizens and audit officers to cross-verify photographic timelines with sanction milestones.

This system provides a unified **multi-engine anomaly detection platform** that ingests the full national MPLADS dataset (~60,000+ records), cross-references expenditure with regional statistical benchmarks, and presents actionable audit findings through an interactive dashboard.

---

## 🚀 Key Capabilities

- **Interactive GIS Heatmap & Constituency Drill-down**: Visualizes projects nationwide using representative geocoded coordinates, color-coded by risk level (Low, Medium, High).
- **Statistical Benchmark & Median Engine**: Calculates category-by-state median costs across all 33 Indian states and UTs to detect abnormal fiscal deviations (e.g. ₹15 Cr civil works vs ₹1.77 L state median).
- **Computer Vision Inspection (YOLOv8)**: Analyzes ground-truth inspection imagery (street-level, drone, and site uploads) across chronological timelines to detect structural defects (potholes, longitudinal cracking, washouts).
- **NLP Duplicate Work Detection**: Leverages sentence embeddings (`all-MiniLM-L6-v2`) and FAISS cosine similarity to catch identical or near-identical descriptions sanctioned within close geographic proximity.
- **Rule-Based AI Audit Assistant**: Chatbot interface allowing auditors to query nationwide data in plain English (e.g. *"Show top high risk road projects in Bihar"* or *"Find projects over 5x median"*).
- **Strict Role-Based Views (Citizen vs. Official)**:
  - **Citizen View**: Public transparency metrics, project progress, sanctioned amounts, and geotagged works.
  - **Official Audit View**: Unmasked anomaly scores, engine breakdown (Financial, Image, NLP), reviewer notes, and one-click Confirm/Dismiss flag review workflow.
- **Secure Passwordless OTP Authentication**: Integrated Node.js auth service with cryptographic email OTP verification and HTTP-only JWT sessions.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Data Sources
        CSV[MPLADS National CSV - 60,000+ records]
        IMG[Site Uploads / Street Imagery]
    end

    subgraph Ingestion & Benchmarking
        PIPE[pipeline/ingest.py]
        SYNC[pipeline/sync_real_anomalies.py]
        BENCH[state-medians.json - 76 State-Category Medians]
    end

    CSV --> PIPE
    PIPE --> DB[(PostgreSQL + PostGIS)]
    CSV --> SYNC
    SYNC --> BENCH

    subgraph Analytical Engines
        FE[Financial Engine - Port 8081\nIsolation Forest & Median Multipliers]
        IE[Image Engine - Port 8082\nYOLOv8 Defect Detection]
        NLP[NLP Similarity Engine - Port 8085\nMiniLM Embeddings & FAISS]
        GS[Graph Service - Port 8083\nVendor NetworkX Collision]
        CE[Cost Estimator - Port 8084\nCivil Work Benchmarking]
    end

    DB --> FE
    DB --> NLP
    IMG --> IE
    DB --> GS

    subgraph Aggregation & Auth
        AUTH[Auth Service - Port 8086\nExpress, SQLite, Email OTP, JWT]
        RA[Risk Aggregator - Port 8080\nFastAPI Gateway & RBAC Filter]
    end

    FE --> RA
    IE --> RA
    NLP --> RA
    GS --> RA
    CE --> FE

    subgraph Frontend Application
        NEXT[Next.js 14 Web App - Port 3000\nTailwind CSS, Leaflet, Role Context]
    end

    AUTH --> NEXT
    RA --> NEXT
    BENCH --> NEXT
```

---

## 📦 Microservices Breakdown

| Service | Technology | Port | Purpose |
|:---|:---|:---:|:---|
| **`frontend`** | Next.js 14, React, Tailwind CSS, Leaflet | `3000` | Responsive web dashboard, project table, interactive map, audit assistant, and flag review modal. |
| **`risk-aggregator`** | Python, FastAPI, Pydantic | `8080` | Central API gateway aggregating signals from all detection engines; enforces Citizen vs. Official data masking. |
| **`financial-engine`** | Python, FastAPI, Scikit-learn, DuckDB | `8081` | Calculates category/state percentile benchmarks and fits Isolation Forest models on project expenditures. |
| **`image-engine`** | Python, FastAPI, Ultralytics YOLOv8 | `8082` | Detects asphalt damage, cracks, potholes, and construction progress from timestamped inspection photos. |
| **`graph-service`** | Python, FastAPI, NetworkX | `8083` | Analyzes contractor-MP networks to detect bidding rings and vendor monopolies. |
| **`cost-estimator`** | Python, FastAPI | `8084` | Civil cost estimation model providing parametric price ranges (road/km, building/sqft). |
| **`nlp-similarity`** | Python, FastAPI, Sentence-Transformers | `8085` | Semantic text embedding and FAISS cosine index for duplicate work detection across constituencies. |
| **`auth-service`** | Node.js, Express, SQLite, Nodemailer | `8086` | Manages official authentication via OTP emails, issuing signed HTTP-only JWTs. |
| **`postgres`** | PostgreSQL 16 + PostGIS 3.4 | `5432` | Primary database storing projects, anomaly flags, inspection metadata, and official audit trails. |

---

## 🔍 Detection Engines

### 1. Financial Anomaly Engine
Calculates the historical median for each `(category, state)` pair:
$$\text{Multiplier} = \frac{\text{Project Allocation}}{\text{Median}_{\text{category, state}}}$$

- **Multiplier $> 5.0\times$**: **High Risk Anomaly** (Score `0.88` - `0.98`), flagged for urgent audit review.
- **Multiplier $> 3.0\times$**: **Moderate Anomaly** (Score `0.75` - `0.85`).
- *Example detected in real data*: Uttarakhand project sanctioned at **₹15,00,00,000** for civil construction against state median of **₹1,77,500** ($845.1\times$ deviation).

### 2. NLP Work Similarity Engine
Uses `all-MiniLM-L6-v2` dense vectors (384 dimensions) to compare work descriptions:
$$\text{Cosine Similarity} = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|}$$
- Flags projects within the same block, MP, or timeframe having similarity $> 0.90$.
- Identifies boilerplate copy-pasted work descriptions sanctioned without independent bills of quantities.

### 3. Computer Vision Image Engine
Uses custom fine-tuned **YOLOv8** weights to process chronological site photos:
- Defect classes: `pothole`, `longitudinal_crack`, `alligator_crack`, `structural_failure`.
- Chronological timeline checks: flags asphalt showing severe potholes within 8–12 months of completion (inconsistent with standard 5–7 year bituminous lifespans).

### 4. Graph & Vendor Collision Service
Constructs bipartite graphs of $(MP \leftrightarrow \text{Contractor})$ and calculates degree centrality and clustering coefficients to surface suspicious vendor concentrations and non-competitive allocations.

---

## 👥 Role-Based Access Control (RBAC)

The application provides dual-mode role authorization:

| Feature | 👤 Citizen Mode | 🏛️ Official Audit Mode |
|:---|:---:|:---:|
| **Project Explorer & GIS Map** | Full access | Full access |
| **Search & State/District Filters** | Full access | Full access |
| **Sanction Amounts & Status** | Visible | Visible |
| **Risk Level (Low / Medium / High)** | Public badge | Public badge |
| **Exact Risk Scores (0.0 - 1.0)** | 🔒 Masked | ✅ Visible |
| **Engine Score Breakdown (NLP, Image, Financial)** | 🔒 Masked | ✅ Visible |
| **Detailed Anomaly Reason & Percentiles** | 🔒 Summarized | ✅ Full forensic report |
| **Audit Review Workflow (Confirm / Dismiss Flag)** | ❌ Read-only | ✅ Interactive with audit notes |
| **Reviewer IDs & Official Logs** | 🔒 Hidden | ✅ Visible |

---

## 🗄️ Database Schema & Data Pipeline

### Core PostgreSQL Tables (`db/migrations/`)
- `mplads_project`: Core table holding all ingested CSV projects, geolocations, allocation amounts, IDA approval status, and SHA-256 row fingerprints for deduplication.
- `anomaly_flag`: Records generated flags, source engine (`financial`, `image`, `nlp`), anomaly scores, reason texts, and `review_status` (`pending`, `confirmed`, `dismissed`).
- `image_capture`: Ground-truth inspection photos, capture dates, sources (`streetview`, `mapillary`, `upload`), and detected defect severities.
- `officials`: Authorized government auditor accounts and role permissions.

### Ingestion & Sync Pipeline (`pipeline/`)
1. `ingest.py`: Parses the raw 15.8 MB `MPLADS.csv` (semicolon-delimited), cleans currency amounts, parses dates, normalizes enums, and inserts batches idempotently into PostgreSQL.
2. `sync_real_anomalies.py`: Analyzes the full dataset using DuckDB, calculates 76 category/state medians, syncs high-risk outliers into `mplads-records.json`, and updates `mock-data.ts`.
3. `export_frontend_dataset.py`: Generates the geocoded dataset with coordinate jittering for map rendering.

---

## 🛠️ Getting Started & Installation

### Prerequisites
- **Node.js** v18+ and **npm**
- **Python** 3.10+ (Python 3.11/3.12 recommended)
- **Docker Desktop** (Optional, for running full containerized stack)

---

### Option A: Full Stack with Docker Compose (Recommended)

To launch the complete infrastructure (Postgres, All 6 ML/Backend Engines, Auth Service, and Frontend):

```bash
# 1. Clone the repository
git clone https://github.com/avinash10002/Anomaly-and-fraud-detection-system.git
cd "Anomaly-and-fraud-detection-system"

# 2. Configure environment files
cp services/auth-service/.env.example services/auth-service/.env
cp pipeline/.env.example pipeline/.env

# 3. Start all services
docker compose up --build -d

# 4. Check running containers
docker compose ps
```
The services will be available at:
- Frontend: `http://localhost:3000`
- Risk Aggregator API: `http://localhost:8080/docs`
- Auth Service: `http://localhost:8086/health`

---

### Option B: Running Locally (Development Mode)

If you wish to run the frontend and services directly on your host machine without Docker:

#### 1. Setup & Start the Frontend (Next.js)
```bash
cd services/frontend
npm install
npm run dev
```
*The frontend will start at `http://localhost:3000`.*

#### 2. Setup & Start the Auth Service
```bash
cd services/auth-service
npm install

# Edit .env to set your SMTP credentials (or keep fallback for mock OTPs)
node src/index.js
```
*The auth service will start at `http://localhost:8086`.*

#### 3. Setup Python ML & Aggregator Services
```bash
# Install root requirements
pip install -r pipeline/requirements.txt
pip install duckdb fastapi uvicorn scikit-learn ultralytics sentence-transformers

# Run Risk Aggregator
cd services/risk-aggregator
python main.py
```

---

## 🔑 Environment Variables

### Auth Service (`services/auth-service/.env`)
```ini
PORT=8086
NODE_ENV=development
JWT_SECRET=your_super_secret_jwt_key_here
JWT_EXPIRES_IN=2h

# Email OTP Configuration (Gmail App Password or SMTP Relay)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_gmail_app_password
SMTP_FROM="MPLADS Audit System <no-reply@mplads.gov.in>"

COOKIE_SECURE=false
COOKIE_SAME_SITE=lax
```

### Risk Aggregator (`services/risk-aggregator/.env`)
```ini
DATABASE_URL=postgresql://mplad_user:mplad_secret@localhost:5432/mplad
SERVICE_PORT=8080
FINANCIAL_ENGINE_URL=http://localhost:8081
IMAGE_ENGINE_URL=http://localhost:8082
NLP_SIMILARITY_URL=http://localhost:8085
```

---

## 📑 API Specification

The REST API contract is documented under [`api/openapi.yaml`](file:///d:/Program%20Files/anamoly%20detector/api/openapi.yaml). 

### Key Endpoints:
- `GET /api/v1/dashboard/stats`: Returns national totals, risk distribution counts, and state summaries.
- `GET /api/v1/projects`: Filter projects by `state`, `constituency`, `category`, `status`, `risk_level`, or keyword search.
- `GET /api/v1/projects/{id}`: Detailed project view including inspection images, NLP similarities, and financial variance analysis.
- `GET /projects/{id}/risk`: Detailed risk assessment, factor breakdown, recommended action, and hedged `stage_indicator` array (`approval_process` vs. `execution_delivery`).
- `PATCH /api/v1/anomaly-flags/{id}`: Official endpoint to **Confirm** or **Dismiss** a flagged anomaly with reviewer notes.
- `POST /api/v1/audit-assistant/query`: Executes natural language analytical queries across the dataset.
- `POST /api/auth/send-otp`: Sends a one-time login passcode to the official's registered email.
- `POST /api/auth/verify-otp`: Validates the passcode and issues an HTTP-only authentication session cookie.

---

## 📁 Project Directory Structure

```text
├── api/
│   └── openapi.yaml                 # OpenAPI 3.0.3 specification
├── data/
│   └── mplads.csv                   # Raw national MPLADS dataset (~60k records)
├── db/
│   ├── migrations/                  # PostgreSQL schema migrations (001 - 004)
│   └── seeds/                       # Demo cases & synthetic baseline seeds
├── pipeline/
│   ├── ingest.py                    # Deduplication & DB ingestion pipeline
│   ├── sync_real_anomalies.py       # DuckDB outlier extraction & frontend sync
│   ├── export_frontend_dataset.py   # Dataset geocoder & formatter
│   └── quality_report.py            # Data hygiene & completeness reporting
├── services/
│   ├── auth-service/                # Express.js OTP Authentication service
│   ├── cost-estimator/              # Civil construction parametric estimator
│   ├── financial-engine/            # Scikit-learn & percentile financial detector
│   ├── frontend/                    # Next.js 14 Web Application
│   │   └── src/
│   │       ├── app/                 # Next.js App Router (Dashboard, Login, Review)
│   │       ├── components/          # Map, ProjectTable, AuditAssistant, Header
│   │       └── lib/                 # API client, State Medians, Role Context
│   ├── graph-service/               # NetworkX vendor graph analysis
│   ├── image-engine/                # YOLOv8 defect & crack detector
│   ├── nlp-similarity/              # Sentence-Transformers duplicate detector
│   └── risk-aggregator/             # Central FastAPI gateway & RBAC layer
├── docker-compose.yml               # Multi-container orchestration specification
└── README.md                        # Project documentation (this file)
```

---

## 📜 License & Compliance

This project is built for governance transparency, public asset integrity, and fiscal accountability under the guidelines of the **Ministry of Statistics and Programme Implementation (MoSPI)**, Government of India. All synthetic demo cases are strictly demarcated with `DEMO_SYNTHETIC` flags to maintain complete data separation from authentic public records.

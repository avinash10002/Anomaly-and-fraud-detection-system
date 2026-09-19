# Deploying to Render (render.com)

This guide provides instructions for deploying the **MPLADS Anomaly & Fraud Detection System** on Render.

---

## Architecture Overview on Render

- **`mplads-frontend`**: Next.js 14 Web Service (Node.js runtime)
- **`mplads-risk-aggregator`**: Central Python FastAPI API Gateway (port `$PORT`)
- **`mplads-financial-engine`**: Statistical Anomaly Detection Engine (FastAPI)
- **`mplads-auth-service`**: Official OTP-over-email Authentication Service (Express.js)
- **`mplads-postgres`**: Managed PostgreSQL Database

---

## Method 1: Automated Blueprint Deployment (Recommended)

A pre-configured [`render.yaml`](./render.yaml) is included in the root of the repository.

1. Go to your [Render Dashboard](https://dashboard.render.com).
2. Click **Blueprints** on the top menu (or **New +** $\rightarrow$ **Blueprint**).
3. Connect your GitHub repository:
   ```
   avinash10002/Anomaly-and-fraud-detection-system
   ```
4. Render will read `render.yaml` and display the list of resources to create:
   - `mplads-frontend` (Web Service)
   - `mplads-risk-aggregator` (Web Service)
   - `mplads-financial-engine` (Web Service)
   - `mplads-auth-service` (Web Service)
   - `mplads-postgres` (PostgreSQL Database)
5. Fill in the prompted secret values for Gmail SMTP:
   - `SMTP_USER`: Your Gmail address (e.g. `yourname@gmail.com`)
   - `SMTP_PASS`: Your 16-character Google App Password (no spaces)
6. Click **Apply**. Render will automatically build, provision, wire the internal networking, and deploy all services!

---

## Method 2: Deploying Individual Services Manually

If you only want to deploy backend microservices on Render (e.g. while hosting the frontend on Vercel):

### 1. Risk Aggregator (`services/risk-aggregator`)
- **Type**: Web Service
- **Runtime**: Python 3
- **Root Directory**: `services/risk-aggregator`
- **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`
- **Environment Variables**:
  ```env
  DATABASE_URL=<your-render-or-external-postgres-connection-string>
  FINANCIAL_ENGINE_URL=https://<your-financial-engine-url>.onrender.com
  ENABLE_AUDIT_ASSISTANT=true
  ```

### 2. Financial Engine (`services/financial-engine`)
- **Type**: Web Service
- **Runtime**: Python 3
- **Root Directory**: `services/financial-engine`
- **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`
- **Environment Variables**:
  ```env
  DATABASE_URL=<your-render-or-external-postgres-connection-string>
  ```

### 3. Auth Service (`services/auth-service`)
- **Type**: Web Service
- **Runtime**: Node
- **Root Directory**: `services/auth-service`
- **Build Command**: `npm install`
- **Start Command**: `node src/scripts/seed.js && node src/index.js`
- **Health Check Path**: `/health`
- **Environment Variables**:
  ```env
  NODE_ENV=production
  JWT_SECRET=<random-64-character-secret>
  JWT_EXPIRES_IN=2h
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=465
  SMTP_SECURE=true
  SMTP_USER=yourname@gmail.com
  SMTP_PASS=your-google-app-password
  SMTP_FROM="MPLADS Audit System <yourname@gmail.com>"
  BCRYPT_ROUNDS=10
  COOKIE_SECURE=true
  COOKIE_SAME_SITE=lax
  ```

---

## Connecting Frontend (Vercel or Render)

In your Frontend configuration, set:
- `NEXT_PUBLIC_API_BASE_URL`: `https://mplads-risk-aggregator.onrender.com/api/v1`
- `AUTH_SERVICE_URL`: `https://mplads-auth-service.onrender.com`

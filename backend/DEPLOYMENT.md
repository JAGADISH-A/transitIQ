# TransitIQ Deployment Guide

## Complete Deployment Documentation for Azure Student Developer ($200 Free Credits)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Azure Student Account Setup](#3-azure-student-account-setup)
4. [Backend Deployment](#4-backend-deployment)
5. [Frontend Deployment](#5-frontend-deployment)
6. [Data Management](#6-data-management)
7. [Environment Configuration](#7-environment-configuration)
8. [Cost Optimization](#8-cost-optimization)
9. [Post-Deployment Verification](#9-post-deployment-verification)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRANSITIQ DEPLOYMENT                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐      ┌──────────────────┐                 │
│  │   FRONTEND       │      │   BACKEND        │                 │
│  │   (Vite/React)   │──────│   (FastAPI)      │                 │
│  │                  │ API  │                  │                 │
│  │ Azure Static     │ Calls│ Azure App        │                 │
│  │ Web Apps         │      │ Service (B1)     │                 │
│  │ (Free Tier)      │      │                  │                 │
│  └──────────────────┘      └────────┬─────────┘                 │
│                                     │                           │
│                                     ▼                           │
│                          ┌──────────────────┐                   │
│                          │   DATA LAYER     │                   │
│                          │                  │                   │
│                          │ - GTFS Files     │                   │
│                          │   (App Service   │                   │
│                          │    File System)  │                   │
│                          │                  │                   │
│                          │ - transit.db     │                   │
│                          │   (SQLite)       │                   │
│                          └──────────────────┘                   │
│                                     │                           │
│                                     ▼                           │
│                          ┌──────────────────┐                   │
│                          │  AZURE OPENAI    │                   │
│                          │  (AI Foundry)    │                   │
│                          │                  │                   │
│                          │  For transit     │                   │
│                          │  assistant AI    │                   │
│                          └──────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

| Component | Service | Cost | Reason |
|-----------|---------|------|--------|
| Frontend | Azure Static Web Apps | **FREE** | Generous free tier, global CDN, custom domains |
| Backend | Azure App Service (B1) | ~$13/month | Managed Python hosting, easy scaling |
| Data | App Service File System | **FREE** | No separate DB needed for GTFS files |
| AI | Azure OpenAI | Pay-per-use | Only used when AI features are called |

**Total Estimated Monthly Cost: ~$13-20/month** (well within $200 credits for ~10 months)

---

## 2. Prerequisites

### Required Software (Local Development)

```bash
# Install Azure CLI
# Windows (PowerShell as Administrator)
winget install Microsoft.AzureCLI

# Or download from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

# Verify installation
az --version
```

### Required Accounts

- [ ] Azure for Students account (free $200 credits)
- [ ] GitHub account (for CI/CD)
- [ ] Azure OpenAI resource (for AI features) - optional but recommended

### Project Structure for Deployment

```
transit-iq/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   ├── services/
│   │   └── models/
│   ├── data/                   # GTFS data files
│   │   ├── Andhra/
│   │   ├── Bangalore/
│   │   ├── Delhi/
│   │   ├── Kochi/
│   │   ├── Mumbai/
│   │   └── Railways/
│   ├── requirements.txt
│   └── transit.db
│
├── frontend/                   # Vite/React frontend
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
│
└── DEPLOYMENT.md              # This file
```

---

## 3. Azure Student Account Setup

### Step 3.1: Activate Azure for Students

1. Go to https://azure.microsoft.com/free/students/
2. Sign in with your school email (.edu)
3. Complete verification
4. You'll receive **$200 free credits** (valid for 12 months)

### Step 3.2: Install Azure CLI & Login

```bash
# Login to Azure
az login

# Set your subscription (if you have multiple)
az account set --subscription "Azure for Students"

# Verify you're on the right subscription
az account show
```

### Step 3.3: Create Resource Group

```bash
# Create a resource group for TransitIQ
az group create \
  --name transitiq-rg \
  --location eastus

# Verify
az group show --name transitiq-rg
```

---

## 4. Backend Deployment

### Step 4.1: Prepare Backend for Deployment

#### 4.1.1: Create Production Requirements

Create `backend/requirements-production.txt`:

```txt
# Production requirements (pinned versions for stability)
fastapi==0.115.0
uvicorn[standard]==0.30.6
pandas==2.2.3
pydantic==2.9.2
pydantic-settings==2.5.2
python-dotenv==1.0.1
azure-identity==1.25.3
openai==1.51.2
rapidfuzz
gunicorn==22.0.0
```

#### 4.1.2: Create Startup Command File

Create `backend/startup.sh`:

```bash
#!/bin/bash
# Startup script for Azure App Service

# Set working directory
cd /home/site/wwwroot

# Install dependencies
pip install -r requirements-production.txt

# Start with gunicorn (production WSGI server)
exec gunicorn app.main:app \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

#### 4.1.3: Create Web.config for Azure

Create `backend/web.config`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="httpplatformhandler" path="*" verb="*"
           modules="httpPlatformHandler"
           resourceType="Unspecified" />
    </handlers>
    <httpPlatform processPath="python"
                  stdoutLogEnabled="true"
                  stdoutLogFile="D:\home\LogFiles\python.log"
                  startupTimeLimit="60"
                  processesPerApplication="1">
      <environmentVariables>
        <environmentVariable name="PYTHONDONTWRITEBYTECODE" value="1" />
        <environmentVariable name="PYTHONUNBUFFERED" value="1" />
      </environmentVariables>
      <processes>
        <process command="gunicorn app.main:app --bind 0.0.0.0:%HTTP_PLATFORM_PORT% --workers 4 --worker-class uvicorn.workers.UvicornWorker --timeout 120">
        </process>
      </processes>
    </httpPlatform>
  </system.webServer>
</configuration>
```

### Step 4.2: Create Azure App Service

#### Option A: Using Azure CLI (Recommended)

```bash
# Create App Service Plan (B1 tier - ~$13/month)
az appservice plan create \
  --name transitiq-plan \
  --resource-group transitiq-rg \
  --sku B1 \
  --is-linux

# Create Web App with Python 3.11
az webapp create \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --plan transitiq-plan \
  --runtime "PYTHON:3.11"

# Configure startup command
az webapp config set \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --startup-file "gunicorn app.main:app --bind 0.0.0.0:8000 --workers 4"

# Enable logging
az webapp log config \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --application-logging filesystem \
  --level information

# Get the URL
az webapp show \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --query defaultHostName \
  --output tsv
```

#### Option B: Using Azure Portal

1. Go to https://portal.azure.com
2. Click **Create a resource** → **Web App**
3. Configure:
   - **Subscription**: Azure for Students
   - **Resource Group**: transitiq-rg
   - **Name**: transitiq-backend
   - **Publish**: Code
   - **Runtime stack**: Python 3.11
   - **Operating System**: Linux
   - **Plan**: Create new → transitiq-plan (B1 tier)
4. Click **Review + Create** → **Create**

### Step 4.3: Deploy Backend Code

#### Option A: Git Deployment (Recommended)

```bash
# Navigate to backend directory
cd backend

# Initialize git (if not already)
git init
git add .
git commit -m "Production deployment"

# Add Azure as remote
az webapp deployment source config-local-git \
  --name transitiq-backend \
  --resource-group transitiq-rg

# Get the git URL
DEPLOYMENT_URL=$(az webapp deployment list-publishing-credentials \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --query scmUri \
  --output tsv)

# Add remote
git remote add azure "$DEPLOYMENT_URL"

# Deploy
git push azure main
```

#### Option B: ZIP Deployment

```bash
# Create deployment package
cd backend
zip -r ../backend-deploy.zip . -x "*.pyc" "__pycache__/*" ".git/*" "tests/*"

# Deploy to Azure
az webapp deployment source config-zip \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --src ../backend-deploy.zip
```

#### Option C: VS Code Extension

1. Install **Azure App Service** extension
2. Press `Ctrl+Shift+P` → **Azure App Service: Deploy to Web App**
3. Select your subscription and `transitiq-backend`
4. Select the `backend` folder

### Step 4.4: Configure Backend Settings

```bash
# Set environment variables
az webapp config appsettings set \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --settings \
    APP_ENV=production \
    GTFS_DATA_PATH=/home/site/wwwroot/data \
    FOUNDRY_MODEL_DEPLOYMENT=gpt-4o-mini \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true

# Set Azure OpenAI credentials (if using)
az webapp config appsettings set \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --settings \
    FOUNDRY_PROJECT_ENDPOINT="your-project-endpoint" \
    FOUNDRY_AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/openai/v1" \
    FOUNDRY_API_KEY="your-api-key"
```

### Step 4.5: Upload GTFS Data

```bash
# Option 1: Using Azure CLI
# Navigate to backend directory
cd backend

# Create a zip of just the data folder
zip -r ../data-deploy.zip data/

# Deploy data via ZIP
az webapp deployment source config-zip \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --src ../data-deploy.zip

# Option 2: Using FTP
# Get FTP credentials
az webapp deployment list-publishing-credentials \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --query "{ftpUrl: ftpUrl, username: userName, password: password}" \
  --output json

# Use an FTP client (FileZilla, WinSCP) to upload the data/ folder
# FTP URL: ftp://transitiq-backend.scm.azurewebsites.net/data/
```

### Step 4.6: Verify Backend Deployment

```bash
# Check if the app is running
az webapp show \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --query state \
  --output tsv

# Test health endpoint
curl https://transitiq-backend.azurewebsites.net/health

# View logs
az webapp log tail \
  --name transitiq-backend \
  --resource-group transitiq-rg
```

---

## 5. Frontend Deployment

### Step 5.1: Configure Frontend for Production

#### 5.1.1: Update API Base URL

Create `frontend/.env.production`:

```env
VITE_API_BASE_URL=https://transitiq-backend.azurewebsites.net
```

#### 5.1.2: Update vite.config.ts

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  }
})
```

#### 5.1.3: Update CORS in Backend

Update `backend/app/main.py` to allow your frontend domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://transitiq-frontend.azurestaticapps.net",  # Your Azure SWA URL
        "http://localhost:5173",  # Local development
        "http://localhost:3000",  # Alternative local port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Step 5.2: Build Frontend

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Build for production
npm run build

# This creates a dist/ folder with optimized files
```

### Step 5.3: Deploy to Azure Static Web Apps

#### Option A: GitHub Actions (Recommended)

1. **Push your code to GitHub**:

```bash
# From project root
git init
git add .
git commit -m "Initial deployment"
git remote add origin https://github.com/yourusername/transit-iq.git
git push -u origin main
```

2. **Create Static Web App in Azure**:

```bash
# Create Static Web App
az staticwebapp create \
  --name transitiq-frontend \
  --resource-group transitiq-rg \
  --source https://github.com/yourusername/transit-iq \
  --branch main \
  --app-location "/frontend" \
  --output-location "dist" \
  --sku Free
```

3. **Configure API Backend**:

```bash
# Link to your backend
az staticwebapp backends link \
  --name transitiq-frontend \
  --resource-group transitiq-rg \
  --backend-host-name transitiq-backend.azurewebsites.net \
  --backend-path-prefix "/api" \
  --sequence 1
```

#### Option B: Azure CLI Direct Deployment

```bash
# Build frontend first
cd frontend
npm run build

# Deploy to Static Web Apps
az staticwebapp deploy \
  --name transitiq-frontend \
  --resource-group transitiq-rg \
  --source "./dist" \
  --branch "production"
```

### Step 5.4: Configure Frontend Settings

```bash
# Add custom domain (optional)
az staticwebapp hostname set \
  --name transitiq-frontend \
  --resource-group transitiq-rg \
  --hostname "transitiq.yourdomain.com"

# View deployment URL
az staticwebapp show \
  --name transitiq-frontend \
  --resource-group transitiq-rg \
  --query defaultHostname \
  --output tsv
```

---

## 6. Data Management

### Understanding Your Data Structure

Your TransitIQ backend uses **GTFS (General Transit Feed Specification)** data organized by region:

```
backend/data/
├── Andhra/           # Andhra Pradesh transit data
│   ├── stops.txt
│   ├── routes.txt
│   ├── trips.txt
│   ├── stop_times.txt
│   ├── shapes.txt
│   ├── tirupati.txt
│   └── vijayawada.txt
│
├── Bangalore/        # Karnataka/Bangalore transit
│   ├── stops.txt
│   ├── routes.txt
│   ├── trips.txt
│   ├── stop_times.txt
│   ├── shapes.txt
│   ├── fare_attributes.txt
│   ├── fare_rules.txt
│   └── translations.txt
│
├── Delhi/            # Delhi transit
│   ├── stops.txt
│   ├── routes.txt
│   ├── trips.txt
│   ├── stop_times.txt
│   └── shapes.txt
│
├── Kochi/            # Kerala/Kochi transit
│   ├── stops.txt
│   ├── routes.txt
│   ├── trips.txt
│   ├── stop_times.txt
│   ├── shapes.txt
│   └── frequencies.txt
│
├── Mumbai/           # Maharashtra/Mumbai transit
│   ├── stops.txt
│   ├── routes.txt
│   ├── trips.txt
│   ├── stop_times.txt
│   └── shapes.txt
│
└── Railways/         # Indian Railways data
    ├── stops.txt
    ├── routes.txt
    ├── trips.txt
    ├── stop_times.txt
    ├── shapes.txt
    └── station_complexes.json
```

### Step 6.1: Compress Data for Deployment

```bash
# Calculate total data size
du -sh backend/data/

# If data is large (>100MB), consider compression
cd backend
tar -czf data.tar.gz data/

# This creates a compressed archive that's faster to upload
```

### Step 6.2: Upload Data to Azure

```bash
# Method 1: ZIP deployment (recommended for large datasets)
cd backend
zip -r ../data-full.zip data/
az webapp deployment source config-zip \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --src ../data-full.zip

# Method 2: FTP upload for incremental updates
# Get FTP credentials
az webapp deployment list-publishing-credentials \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --query "{ftpUrl: ftpUrl, username: userName, password: password}"
```

### Step 6.3: Verify Data Upload

```bash
# SSH into App Service to verify
az webapp ssh \
  --name transitiq-backend \
  --resource-group transitiq-rg

# Once connected, check data directory
ls -la /home/site/wwwroot/data/
ls -la /home/site/wwwroot/data/Bangalore/
```

### Step 6.4: Data Persistence

**Important**: Azure App Service file system is **persistent** but has limitations:

- ✅ Files persist across app restarts
- ✅ Files persist across deployments (if not overwritten)
- ⚠️ 1 GB storage limit on B1 tier
- ⚠️ Files are lost if you delete the App Service

**Backup Strategy**:

```bash
# Create backup of data
az webapp config backup create \
  --resource-group transitiq-rg \
  --webapp-name transitiq-backend \
  --backup-name transitiq-data-backup \
  --container-url "https://yourstorage.blob.core.windows.net/backups?sv=2022-11-02&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2024-12-31&spr=https&sig=your-sas-token"
```

---

## 7. Environment Configuration

### Step 7.1: Create .env for Production

Create `backend/.env.production`:

```env
# Application Settings
APP_NAME=TransitIQ
APP_VERSION=1.0.0
APP_ENV=production

# GTFS Data Path (Azure App Service path)
GTFS_DATA_PATH=/home/site/wwwroot/data

# Azure OpenAI Configuration (Optional - for AI features)
FOUNDRY_PROJECT_ENDPOINT=
FOUNDRY_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/openai/v1
FOUNDRY_PROJECT_OPENAI_ENDPOINT=
FOUNDRY_MODEL_DEPLOYMENT=gpt-4o-mini
FOUNDRY_API_KEY=your-api-key-here
```

### Step 7.2: Configure Azure App Settings

```bash
# Set all environment variables at once
az webapp config appsettings set \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --settings \
    APP_NAME=TransitIQ \
    APP_VERSION=1.0.0 \
    APP_ENV=production \
    GTFS_DATA_PATH=/home/site/wwwroot/data \
    FOUNDRY_MODEL_DEPLOYMENT=gpt-4o-mini \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    ENABLE_ORYX_BUILD=true \
    PYTHON_ENABLE_WORKER_EXTENSIONS=1
```

### Step 7.3: Configure Azure OpenAI (Optional)

If you want AI-powered transit assistant features:

```bash
# 1. Create Azure OpenAI resource
az cognitiveservices account create \
  --name transitiq-openai \
  --resource-group transitiq-rg \
  --kind OpenAI \
  --sku S0 \
  --location eastus

# 2. Deploy a model
az cognitiveservices account deployment create \
  --name transitiq-openai \
  --resource-group transitiq-rg \
  --deployment-name gpt-4o-mini \
  --model-name gpt-4o-mini \
  --model-version "2024-05-13" \
  --model-format OpenAI \
  --sku-capacity 1 \
  --sku-name "GlobalStandard"

# 3. Get the endpoint and key
az cognitiveservices account show \
  --name transitiq-openai \
  --resource-group transitiq-rg \
  --query properties.endpoint

az cognitiveservices account keys list \
  --name transitiq-openai \
  --resource-group transitiq-rg \
  --query key1
```

---

## 8. Cost Optimization

### Azure for Students Budget Breakdown

| Service | Tier | Monthly Cost | Credits Remaining (Starting: $200) |
|---------|------|--------------|-------------------------------------|
| App Service (Backend) | B1 Linux | ~$13.14 | $186.86 (Month 1) |
| Static Web Apps (Frontend) | Free | $0.00 | $186.86 |
| Azure OpenAI (Optional) | Pay-per-use | ~$2-5 | ~$181-184 |
| **Total** | | **~$13-18/month** | **~$180-187** |

### Estimated Duration on $200 Credits

- **Without AI**: ~15 months ($13/month)
- **With AI (light usage)**: ~10-12 months ($18/month)
- **With AI (heavy usage)**: ~8-10 months ($22/month)

### Cost Optimization Tips

```bash
# 1. Stop App Service when not in use (saves ~$13/month)
az webapp stop \
  --name transitiq-backend \
  --resource-group transitiq-rg

# 2. Start it back up
az webapp start \
  --name transitiq-backend \
  --resource-group transitiq-rg

# 3. Check current costs
az consumption usage list \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --query "[].{date:usageStart, cost:pretaxCost}" \
  --output table

# 4. Set spending alerts
az monitor activity-log alert create \
  --name "transitiq-cost-alert" \
  --resource-group transitiq-rg \
  --condition "category=Administrative and operationName='Microsoft.Consumption/usageDetails/write'" \
  --action-group "/subscriptions/{subscription-id}/resourceGroups/transitiq-rg/providers/microsoft.insights/actionGroups/your-action-group"
```

### Alternative: Use Free Tier for Testing

```bash
# Create F1 (Free) tier App Service Plan for testing
az appservice plan create \
  --name transitiq-plan-free \
  --resource-group transitiq-rg \
  --sku F1 \
  --is-linux

# Note: Free tier has limitations:
# - 60 minutes compute time per day
# - 1 GB storage
# - No custom domains
# - Good for development/testing only
```

---

## 9. Post-Deployment Verification

### Step 9.1: Test Backend API

```bash
# Test health endpoint
curl https://transitiq-backend.azurewebsites.net/health

# Expected response:
# {"status": "healthy", "feeds_loaded": 6}

# Test stops endpoint
curl "https://transitiq-backend.azurewebsites.net/stops/search?query=Bangalore"

# Test feeds endpoint
curl https://transitiq-backend.azurewebsites.net/feeds
```

### Step 9.2: Test Frontend

```bash
# Open in browser
# https://transitiq-frontend.azurestaticapps.net

# Or use curl to verify it's serving
curl -I https://transitiq-frontend.azurestaticapps.net

# Expected headers:
# HTTP/2 200
# content-type: text/html
```

### Step 9.3: Test Full Integration

1. Open your Static Web Apps URL in a browser
2. Try searching for stops in different cities
3. Test trip planning between two stops
4. Verify the AI assistant responds (if configured)

### Step 9.4: Monitor Performance

```bash
# Enable Application Insights
az monitor app-insights component create \
  --app transitiq-insights \
  --resource-group transitiq-rg \
  --location eastus

# Link to App Service
az webapp config appsettings set \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --settings "APPINSIGHTS_INSTRUMENTATIONKEY=your-key"

# View metrics in Azure Portal
# https://portal.azure.com → App Service → Monitoring → Metrics
```

---

## 10. Troubleshooting

### Common Issues and Solutions

#### Issue 1: App Service Won't Start

```bash
# Check logs
az webapp log tail \
  --name transitiq-backend \
  --resource-group transitiq-rg

# Common causes:
# - Missing dependencies in requirements.txt
# - Wrong Python version
# - Import errors

# Fix: Ensure requirements.txt includes all dependencies
pip freeze > requirements.txt
```

#### Issue 2: GTFS Data Not Found

```bash
# Verify data path in App Settings
az webapp config appsettings list \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --query "[?name=='GTFS_DATA_PATH']"

# Should be: /home/site/wwwroot/data

# Check if data exists
az webapp ssh \
  --name transitiq-backend \
  --resource-group transitiq-rg

# Then: ls -la /home/site/wwwroot/data/
```

#### Issue 3: CORS Errors

```bash
# Update CORS settings in App Service
az webapp cors add \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --allowed-origins "https://transitiq-frontend.azurestaticapps.net"

# Or update in code and redeploy
```

#### Issue 4: Deployment Fails

```bash
# Check deployment logs
az webapp deployment log \
  --name transitiq-backend \
  --resource-group transitiq-rg

# Common issues:
# - Large data files (>100MB) - use ZIP deployment
# - Missing startup file
# - Build errors

# Force redeploy
az webapp deployment source sync \
  --name transitiq-backend \
  --resource-group transitiq-rg
```

#### Issue 5: Cold Start Slow

```bash
# Enable Always On (requires B1 tier or higher)
az webapp config set \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --always-on true

# Pre-warm the app
curl https://transitiq-backend.azurewebsites.net/health
```

---

## Quick Reference Commands

### Essential Azure CLI Commands

```bash
# Login
az login

# List resources
az resource list --resource-group transitiq-rg

# Check App Service status
az webapp show \
  --name transitiq-backend \
  --resource-group transitiq-rg \
  --query state

# View logs
az webapp log tail \
  --name transitiq-backend \
  --resource-group transitiq-rg

# SSH into App Service
az webapp ssh \
  --name transitiq-backend \
  --resource-group transitiq-rg

# Stop/Start to save costs
az webapp stop --name transitiq-backend --resource-group transitiq-rg
az webapp start --name transitiq-backend --resource-group transitiq-rg

# Deploy code
az webapp deployment source config-local-git \
  --name transitiq-backend \
  --resource-group transitiq-rg

# View costs
az consumption usage list \
  --start-date $(date -d "1 month ago" +%Y-%m-%d) \
  --end-date $(date +%Y-%m-%d)
```

### Useful URLs

| Service | URL |
|---------|-----|
| Azure Portal | https://portal.azure.com |
| App Service URL | https://transitiq-backend.azurewebsites.net |
| Frontend URL | https://transitiq-frontend.azurestaticapps.net |
| API Docs | https://transitiq-backend.azurewebsites.net/docs |
| Health Check | https://transitiq-backend.azurewebsites.net/health |

---

## Next Steps After Deployment

1. **Set up CI/CD**: Configure GitHub Actions for automatic deployments
2. **Add Custom Domain**: Map your own domain to Static Web Apps
3. **Enable HTTPS**: Force HTTPS for security
4. **Set Up Monitoring**: Configure alerts for errors and performance
5. **Backup Strategy**: Regular backups of GTFS data
6. **Scale Up**: If needed, upgrade to higher tiers

---

## Support and Resources

- **Azure Documentation**: https://docs.microsoft.com/azure
- **Azure for Students**: https://azure.microsoft.com/free/students/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Vite Documentation**: https://vitejs.dev/

---

**Last Updated**: June 2026  
**Version**: 1.0.0  
**Maintainer**: TransitIQ Team

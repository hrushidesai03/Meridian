# Meridian — Complete Setup 

**Estimated setup time: 25-35 minutes** (depending on download speeds)

This guide provides step-by-step instructions to run Meridian on your laptop. Every terminal command is provided.

---

## ⚠️ CRITICAL: API Keys & Environment

Meridian requires API keys that are **NOT included in the GitHub repository** for security.

You must:
1. Create your own free accounts at MongoDB, VideoDB, and Groq
2. Create a `.env` file in the `backend` folder with your own keys
3. See **Step 7** below for the complete template

---

## Part 1: Install Required Software

Install these tools on your system **before cloning Meridian**:

### 1a. Install Python 3.10+

**Windows:**
- Download: https://www.python.org/downloads/
- Run installer, check "Add Python to PATH"
- Verify: Open PowerShell and run `python --version`

**Mac:**
```bash
brew install python@3.10
```

**Linux:**
```bash
sudo apt-get install python3.10
```

### 1b. Install Node.js 18+

**Windows/Mac:**
- Download: https://nodejs.org (LTS version)
- Run installer, follow defaults
- Verify: Open PowerShell and run `node --version` and `npm --version`

**Linux:**
```bash
sudo apt-get install nodejs npm
```

### 1c. Install Git

**Windows:**
- Download: https://git-scm.com/download/win
- Run installer, accept defaults
- Verify: `git --version`

**Mac:**
```bash
brew install git
```

**Linux:**
```bash
sudo apt-get install git
```

### 1d. Install Tesseract OCR

**Windows:**
1. Download installer: https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe
2. Run the installer
3. Choose installation path: `C:\Program Files\Tesseract-OCR\` (default is fine)
4. Complete installation

**Mac:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr
```

### 1e. Install ngrok

1. Download: https://ngrok.com/download
2. Extract to a folder
3. Add to PATH or run from extracted folder
4. Verify: `ngrok --version`

---

## Part 2: Create Free Online Accounts

Create accounts at these services (all free, no credit card needed):

### 2a. MongoDB Atlas

1. Go to https://cloud.mongodb.com
2. Sign up (free)
3. Create a new project
4. Create a cluster → Choose **M0 Free Tier**
5. Create a database user:
   - Choose "Autogenerate Secure Password"
   - Save the username and password
6. Under **Network Access** → Click **Add IP Address** → Select **Allow Access from Anywhere** (for development)
7. Click **Connect** → Choose **Drivers** → Select **Python 3.10 or later**
8. Copy the connection string. It looks like:
   ```
   mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   ```
   Replace `<password>` with your actual password

**Save this connection string — you'll need it for Step 7**

### 2b. VideoDB

1. Go to https://console.videodb.io
2. Sign up (free $20 credits, no card needed)
3. After login, click **API Keys & SDK** in the left sidebar
4. Copy your API key (starts with `sk-`)

**Save this key — you'll need it for Step 7**

### 2c. Groq

1. Go to https://console.groq.com
2. Sign up (completely free, no card needed)
3. After login, click **API Keys** in the left menu
4. Click **Create API Key**
5. Copy the key (starts with `gsk_`)

**Save this key — you'll need it for Step 7**

---

## Part 3: Clone & Setup Meridian

### 3a. Clone the Repository

Open PowerShell/Terminal and run:

```bash
git clone https://github.com/meridian-team/meridian.git
cd meridian
```

### 3b. Create Python Virtual Environment

**Windows (PowerShell):**
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Mac/Linux (Bash):**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your terminal should now show `(.venv)` at the beginning of the line.

### 3c. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This will take 2-5 minutes to download and install all packages.

### 3d. Install Node Dependencies

Open a **new terminal** (you don't need to deactivate the virtual env):

```bash
cd meridian/dashboard
npm install
```

This will take 2-5 minutes.

---

## Part 4: Create Environment Configuration

Create a file named `.env` inside the `backend` folder with your API keys:

**File location:** `meridian/backend/.env`

**Content (replace the placeholder values with your actual keys from Part 2):**

```env
# MongoDB Connection String
# Get this from Step 2a (MongoDB Atlas)
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DB=meridian

# VideoDB API Key
# Get this from Step 2b (VideoDB console)
VIDEODB_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
VIDEODB_API_ENDPOINT=https://api.videodb.io

# Groq API Key
# Get this from Step 2c (Groq console)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx

# ngrok URL (from Step 5 below - you'll update this)
CALLBACK_BASE_URL=https://xxxxxxx.ngrok-free.app

# Application Settings
APP_NAME=Meridian
ENVIRONMENT=development
DEBUG=true
VIDEODB_WEBHOOK_SECRET=meridian_secret_123
WS_HEARTBEAT_INTERVAL=30
MAX_WORKERS=4
TRANSCRIPT_BATCH_TIMEOUT_SECONDS=5
```

**IMPORTANT:** Replace the three `xxx...` values with your actual keys from Part 2.

---

## Part 5: Start ngrok Tunnel

Open a **new terminal** (keeping the previous ones running):

```bash
ngrok http 8000
```

You will see output like:

```
Forwarding https://abc123def456.ngrok-free.app -> http://localhost:8000
```

**Copy the `https://abc123def456.ngrok-free.app` URL**

### Update Your .env File

Edit `meridian/backend/.env` and update:

```env
CALLBACK_BASE_URL=https://abc123def456.ngrok-free.app
```

Use the actual URL from your ngrok output.

**Keep this terminal running throughout your testing.**

---

## Part 6: Start the Backend Server

In your **first terminal** (where you have the virtual env activated):

```bash
cd meridian/backend
uvicorn main:app --reload --port 8000
```

Wait for this output:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### Verify Backend is Working

Open your browser and go to: http://localhost:8000/health

You should see:
```json
{"status": "healthy"}
```

**Keep this terminal running.**

---

## Part 7: Start the Dashboard

In your **second terminal**:

```bash
cd meridian/dashboard
npm run dev
```

Wait for this output:

```
Ready on http://localhost:3000
```

### Verify Dashboard is Working

Open your browser and go to: http://localhost:3000

You should see the Meridian dashboard (empty at first, which is normal).

**Keep this terminal running.**

---

## Part 8: Open the Capture Client

In your browser, open: `meridian/capture-client/index.html`

You can do this by:
- File Explorer → navigate to the meridian folder → double-click `capture-client/index.html`
- Or type in browser address bar: `file:///C:/path/to/meridian/capture-client/index.html`

---

## Summary: What Should Be Running

You should now have **four things running simultaneously:**

| Window | What | Status |
|--------|------|--------|
| **Terminal 1** | Backend Server | `uvicorn main:app --reload --port 8000` → Running on port 8000 |
| **Terminal 2** | Dashboard | `npm run dev` → Running on port 3000 |
| **Terminal 3** | ngrok Tunnel | `ngrok http 8000` → Forwarding to localhost:8000 |
| **Browser Tab 1** | Dashboard | http://localhost:3000 |
| **Browser Tab 2** | Capture Client | file:///path/to/capture-client/index.html |

---

## How to Use Meridian

### Feature 1: Extract Commitments from a Meeting

1. Open the **Capture Client** in your browser
2. Select **"Meeting"** from the session type dropdown
3. Click **"Start Capture Session"**
4. Allow microphone access when prompted
5. Speak naturally and make commitments:
   - *"I will refactor the authentication service by Thursday"*
   - *"We are going with PostgreSQL, not MongoDB"*
6. Stop the session
7. Go to **http://localhost:3000** (Dashboard)
8. Commitments will appear in the **Commitments** tab within 10 seconds
9. Decisions will appear in the **Decisions** tab

### Feature 2: Detect Decision Drift (Code vs. Decisions)

1. Open the **Capture Client**
2. Select **"Work Session"** from the session type dropdown
3. Click **"Start Capture Session"**
4. Allow screen share when prompted
5. Open VS Code and type code that **contradicts a decision** you made. For example:
   - If you decided "use PostgreSQL", type: `const mongoose = require('mongoose');`
   - If you decided "don't use MongoDB", type: `db.collection('users').find()`
6. Wait **30 seconds** for Meridian to analyze
7. Go to the **Alerts** tab in the dashboard
8. You will see a **HIGH SEVERITY** drift alert

### Feature 3: Generate Sprint Retrospective

1. Go to **http://localhost:3000**
2. Click the **Retro** tab
3. Click **"Generate Retro"**
4. Wait 5 seconds
5. A full sprint report appears showing:
   - Commitments delivered vs. missed
   - Decisions that held vs. drifted
   - AI recommendations for next sprint

---

## Troubleshooting

### "ModuleNotFoundError" when starting backend

**Solution:**
```bash
cd meridian/backend
pip install -r requirements.txt
```

### Backend shows "pydantic validation error"

**Solution:** Check your `.env` file in `meridian/backend/.env`
- Make sure **all values are filled in** (no placeholders like `your_api_key_here`)
- Make sure the MongoDB URL includes your actual password (not `<password>`)
- Save the file and restart the backend

### Dashboard shows "No data" or connection errors

**Solution:**
1. Make sure backend is running: http://localhost:8000/health should return `{"status": "healthy"}`
2. Check browser console (F12) for CORS errors
3. Make sure backend is on port 8000 and dashboard on port 3000

### "Failed to fetch" in Capture Client

**Solution:** Backend is not running. Go to Terminal 1 and make sure `uvicorn main:app --reload --port 8000` is running and shows "Application startup complete"

### No commitments appear after speaking

**Solution:**
1. Check Terminal 1 (backend) for Groq API errors
2. Make sure `GROQ_API_KEY` in `.env` is correct
3. Make sure you spoke clearly and made an actual commitment (not just noise)

### Drift detection not working

**Solution:**
1. Make sure Tesseract is installed correctly
2. On Windows: Check that `C:\Program Files\Tesseract-OCR\tesseract.exe` exists
3. Make sure you're typing clear text (not just random characters)

### ngrok URL keeps changing

**Solution:**
- Each time ngrok restarts, it gets a new URL
- Update `CALLBACK_BASE_URL` in `.meridian/backend/.env`
- Restart the backend server

---

## Project File Structure

```
meridian/
├── backend/                    # Python FastAPI backend
│   ├── agents/
│   │   └── orchestration.py    # Core agents: Commitment, Decision, Gap, Drift detection
│   ├── database/
│   │   ├── db.py               # MongoDB connection setup
│   │   └── models.py           # Data model definitions
│   ├── routers/
│   │   ├── sessions.py         # Session management + audio/screen processing
│   │   ├── commitments.py      # Commitments API endpoints
│   │   ├── decisions.py        # Decisions API endpoints
│   │   ├── alerts.py           # Alerts API endpoints
│   │   ├── reports.py          # Sprint retrospective generation
│   │   └── webhooks.py         # VideoDB webhook handlers
│   ├── services/
│   │   ├── claude_service.py   # All Groq LLM API calls (Whisper, Llama)
│   │   └── videodb_service.py  # VideoDB SDK integration
│   ├── scheduler.py            # Background job scheduler for gap detection
│   ├── config.py               # Environment configuration
│   ├── main.py                 # FastAPI app entry point
│   ├── requirements.txt        # Python package dependencies
│   └── .env                    # **CREATE THIS** with your API keys
│
├── dashboard/                  # Next.js React frontend
│   ├── app/
│   │   ├── page.tsx            # Main dashboard page
│   │   ├── layout.tsx          # App layout and styling
│   │   └── globals.css         # Global CSS
│   ├── components/
│   │   ├── CommitmentsTable.tsx    # Commitments with confidence scores
│   │   ├── DecisionsTable.tsx      # Decisions with drift status
│   │   ├── DriftAlerts.tsx         # Alert cards with evidence
│   │   ├── RetroPanel.tsx          # Sprint retrospective report
│   │   └── SessionControl.tsx      # Session start/stop buttons
│   ├── lib/
│   │   └── api.ts              # API client for backend
│   ├── package.json            # Node dependencies
│   └── next.config.ts          # Next.js configuration
│
├── capture-client/
│   └── index.html              # Browser-based capture UI (no build needed)
│
├── README.md                   # Project overview and features
├── SETUP.md                    # This setup guide
└── .gitignore                  # Git ignore patterns
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | FastAPI (Python 3.10+) |
| **Database** | MongoDB Atlas (cloud) |
| **Real-time Audio** | VideoDB RTStream + Groq Whisper |
| **LLM Processing** | Groq Llama 3.3 70B |
| **OCR** | Tesseract |
| **Frontend** | Next.js 15 + React + Tailwind CSS |
| **Scheduling** | APScheduler |
| **Public Tunnel** | ngrok (for webhooks) |

---

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check if backend is running |
| `/sessions/create` | POST | Start a capture session |
| `/sessions/audio-chunk` | POST | Send audio chunk for transcription |
| `/sessions/screenshot` | POST | Send screenshot for drift detection |
| `/commitments?end_user_id=xxx` | GET | Get all commitments for a user |
| `/decisions?end_user_id=xxx` | GET | Get all decisions for a user |
| `/alerts?end_user_id=xxx` | GET | Get all alerts for a user |
| `/retro` | POST | Generate sprint retrospective |
| `/webhooks/videodb` | POST | VideoDB webhook (internal) |

---

## Questions?

If something doesn't work:

1. **Check terminal output** — look for error messages
2. **Verify all three services are running** — backend, dashboard, ngrok
3. **Check your .env file** — all keys filled in correctly
4. **Check MongoDB connection** — make sure you used the right connection string
5. **Restart services** — stop and restart the terminal that's having issues

---

**Built for the VideoDB Global Hackathon — May 2026**
Theme: Give Agents Eyes and Ears

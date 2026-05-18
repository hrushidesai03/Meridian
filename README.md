# Meridian

**Meridian is the only tool that automatically detects when your team breaks their promises — by watching what they actually build.**

---

## The Problem

Every team has this moment:

> **Monday standup:** *"I'll refactor the auth service by Thursday. And we're using PostgreSQL, not MongoDB."*
>
> **Thursday:** Auth untouched. MongoDB code quietly committed.
>
> **Friday retro:** *"Why didn't this ship?"*

Commitments get forgotten. Decisions get ignored. Nobody catches it until it's too late.

**Meridian catches it the moment it happens.**

---

## What Meridian Does

Meridian automatically watches two things:

### 1. **Meeting Sessions** 🎤
- Listens to your standup or planning meeting through the microphone
- Extracts every commitment and technical decision made
- Scores how confident the speaker actually sounded (0-100)
- Stores them with deadlines and context

### 2. **Work Sessions** 💻
- Captures your screen every 30 seconds while you code
- Reads the code using OCR
- Checks it against the decisions your team made
- **Alerts instantly when contradiction appears**

---

## Two Core Features

### Feature 1: Decision Drift Detection
Your team decided PostgreSQL. Three days later, Mongoose appears in someone's editor.

Meridian sees it. Immediately.

```
Decision: "We're using PostgreSQL, not MongoDB"
Screen capture: "const mongoose = require('mongoose')"
                        ↓
                    DRIFT ALERT 🚨
```

### Feature 2: Commitment Gap Detection
Your teammate said *"I'll fix the auth bug by Thursday."* It's now Sunday.

Meridian noticed. Nobody else did.

```
Commitment: "fix auth by Thursday"
Deadline passed + no auth-related work found on screen
                        ↓
                    GAP ALERT 🚨
```

### Feature 3: Sprint Retrospective
One click generates a full sprint report:
- ✅ Commitments delivered
- ⏱️ Commitments missed
- 🔄 Decisions that held
- ⚠️ Decisions that drifted
- 💡 AI recommendations for next sprint

---

## How It Works

```
Meeting mic 🎤
    ↓
VideoDB RTStream
    ↓
Groq Whisper (transcription)
    ↓
Groq Llama 3.3 70B (extract commitments + decisions)
    ↓
MongoDB (persistent storage)
    ↓
Dashboard shows confidence scores + status

Screen capture 💻
    ↓
Tesseract OCR (read text from screenshots)
    ↓
Check against active decisions
    ↓
Contradiction found? → DRIFT ALERT 🚨
    ↓
Dashboard + email notification
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI (Python 3.10+) |
| **Database** | MongoDB Atlas |
| **Real-time Capture** | VideoDB RTStream + Webhooks |
| **Transcription** | Groq Whisper Large V3 |
| **LLM Processing** | Groq Llama 3.3 70B |
| **OCR** | Tesseract |
| **Frontend** | Next.js 15 + React + Tailwind CSS |
| **Scheduler** | APScheduler |
| **Public Tunnel** | ngrok (for webhooks) |

---

## VideoDB Primitives Used

Meridian leverages the following **VideoDB APIs and features** to achieve real-time monitoring:

### 1. **Capture Sessions** 
- `create_capture_session()` — Initiates audio/screen capture with webhook callbacks
- `generate_client_token()` — Embeds capture widget in frontend for browser-based capture

### 2. **Real-Time Streaming (RTStream)**
- `get_rtstream()` — Retrieves live streaming object from VideoDB
- `index_visuals()` — Indexes visual frames for OCR processing of screen captures
- Real-time visual indexing for drift detection on code changes

### 3. **Webhooks for Event-Driven Pipeline**
- `capture.completed` — Triggered when recording session ends
- `rtstream.ready` — Fired when RTStream is ready for indexing
- `transcript.chunk` — Delivers transcription chunks for real-time processing
- Webhooks trigger full AI pipeline: commitment extraction → decision checking → drift alerts

### 4. **Video Timeline & Editing**
- `Timeline`, `Track`, `Clip` — Builds "accountability receipt" video compilations
- `Subtitle` — Adds annotations for violations (timestamp-tagged)
- `generate()` — Renders final evidence video with violations highlighted

### 5. **Collection Management**
- `get_collection()` — Accesses stored RTStreams for retrieval and processing
- Enables multi-session storage and historical replay

**Why VideoDB?** Meridian watches *actual work* happening in real-time. VideoDB's RTStream + webhooks make it possible to capture, process, and react to real-time video frames without storing raw video files — we only extract and store the text that matters.

---

## 🚀 How to Run Meridian

### Quick Prerequisites
- **Python 3.10+** — [Download](https://www.python.org/downloads/)
- **Node.js 18+** — [Download](https://nodejs.org)
- **Free API accounts:**
  - [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) (create cluster)
  - [VideoDB Console](https://console.videodb.io) (get API key)
  - [Groq Console](https://console.groq.com) (get API key)

### Installation (4 Steps, ~5 minutes)

**Step 1:** Clone and enter directory
```bash
git clone https://github.com/hrushidesai03/Meridian.git
cd Meridian
```

**Step 2:** Create backend environment file
```bash
cd backend
cp .env.example .env
# Edit .env with your API keys:
# - MONGODB_URL (from Atlas)
# - VIDEODB_API_KEY (from VideoDB)
# - GROQ_API_KEY (from Groq)
# - CALLBACK_BASE_URL (see Step 4)
```

**Step 3:** Start backend in Terminal 1
```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Step 4:** Start ngrok tunnel in Terminal 2 (for webhooks)
```bash
ngrok http 8000
# Copy the "Forwarding" URL and paste into backend/.env as CALLBACK_BASE_URL
# Restart main.py
```

**Step 5:** Start frontend in Terminal 3
```bash
cd dashboard
npm install
npm run dev
# Opens at http://localhost:3000
```

**Step 6:** Open your browser
- Dashboard: http://localhost:3000
- Click "Start Session" to begin capturing
- Speak commitments, then capture screen
- Watch alerts appear in real-time

### Full Setup Guide
For detailed troubleshooting, feature walkthrough, and API reference: **[See SETUP.md](./SETUP.md)**

---

## Quick Start (Legacy)

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Health check |
| `POST /sessions/create` | Start capture session |
| `POST /sessions/audio-chunk` | Send audio for transcription |
| `POST /sessions/screenshot` | Send screenshot for drift detection |
| `GET /commitments?end_user_id=xxx` | List commitments |
| `GET /decisions?end_user_id=xxx` | List decisions |
| `GET /alerts?end_user_id=xxx` | List alerts |
| `POST /retro` | Generate sprint retrospective |

---

## Project Structure

```
meridian/
├── backend/                  # FastAPI backend
│   ├── agents/               # CommitmentAgent, DriftDetector, GapDetector
│   ├── database/             # MongoDB models
│   ├── routers/              # API endpoints
│   ├── services/             # Groq LLM + VideoDB
│   ├── requirements.txt      # Python dependencies
│   └── main.py               # Entry point
├── dashboard/                # Next.js frontend
│   ├── app/                  # Pages
│   ├── components/           # React components
│   └── package.json          # Node dependencies
├── capture-client/           # Browser capture UI
│   └── index.html            # No build needed
├── README.md                 # This file
└── SETUP.md                  # Detailed setup guide
```

---

## Why This Matters

Every tool in the meeting space — Notion, Linear, Jira, Slack — requires someone to **manually** update something. Someone writes the task. Someone moves the card. Someone closes the ticket.

**The moment it becomes manual, it stops happening.**

Meridian is fully automatic. The developer just works. Meridian watches.

---

## Key Insights

**Confidence Scoring:**
Not all commitments are equal. Meridian scores each 0-100 based on:
- Strong language? ("I will" vs "I might")
- Specific deadline?
- Self-proposed or reluctant?
- Hedging words? ("maybe", "probably")

**Multi-user Support:**
Each user has a unique `end_user_id`. Sessions, commitments, decisions, and alerts are all scoped per user. Teams can run simultaneously.

**Security:**
- Screenshots are taken locally in the browser
- Only extracted text is stored in MongoDB
- No video files saved
- API keys stored in `.env` (not in repo)

---

## Built For

**VideoDB Global Hackathon — May 2026**  
**Theme:** *Give Agents Eyes and Ears*

### Why This Hackathon Submission?

Meridian fully embodies the hackathon theme:
- **Eyes 👀** — Screen capture + OCR detects code changes *as they happen*
- **Ears 👂** — Audio capture + transcription extracts spoken commitments
- **AI Agent 🤖** — CommitmentAgent + DriftDetector automatically monitors for violations
- **Real-time Action ⚡** — VideoDB webhooks trigger instant alerts to team

VideoDB is essential to the product — without RTStream and webhooks, this wouldn't work.

---

## Questions?

**Setup issues?** See **[SETUP.md](./SETUP.md)** for detailed troubleshooting  
**How do I use it?** Read the Feature Walkthrough section below in SETUP.md  
**API reference?** Check **[SETUP.md](./SETUP.md)** API Endpoints section

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

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Free accounts: MongoDB Atlas, VideoDB, Groq

### Setup (25-35 minutes)

See **[SETUP.md](./SETUP.md)** for complete step-by-step instructions including:
- ✅ All software downloads
- ✅ All terminal commands
- ✅ API key creation (MongoDB, VideoDB, Groq)
- ✅ Running the system (4 terminals)
- ✅ Testing all features
- ✅ Troubleshooting

---

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
Theme: *Give Agents Eyes and Ears*

---

## Questions?

See **[SETUP.md](./SETUP.md)** for:
- Detailed setup instructions
- Troubleshooting guide
- Feature walkthrough
- API reference

# **Sentinel.AI – Autonomous Misinformation Defense System**

Sentinel AI is a real-time autonomous threat-intelligence engine designed to detect and neutralize lethal misinformation. Built on a Gemini 2.5 agentic pipeline (LangGraph), it ingests live data, cross-references claims with trusted sources, and produces high-confidence, fully traceable verdicts.  
Its **Live War Room Dashboard** replaces passive reporting with active, real-time crisis defense.

--- **Demo Link** :

## **✨ Core Innovations & Features**

### **1. Zero-Latency, API-Free Data Intake**
A fully autonomous Signal Intake Engine eliminates slow and costly news APIs. It ingests:

- Government RSS feeds (NDMA, IMD, GDACS)
- Real-time social discovery via DuckDuckGo
- Global fact-checker feeds (AltNews, Snopes, AFP)

**Benefits:**
- Zero ingestion cost  
- Instant “first-heartbeat” crisis detection  
- Prioritizes verified, authoritative sources  

---

### **2. Cognitive Agentic Triangulation (Council of Agents)**
A LangGraph Orchestrator coordinates three reasoning agents:

- **Official Checker** – Scrapes authoritative government sources (.gov.in, NDMA, Police)
- **Media Cross-Referencer** – Confirms claims using Tier-1 outlets (Reuters, BBC, India Today)
- **Debunker Agent** – Matches claims with global fact-check archives, detecting recycled “zombie rumors”

A Gemini 2.5 reasoning layer synthesizes their findings using structured logic, cross-verification, and “absurdity checks,” producing confidence-scored verdicts.

---

### **3. Live War Room Defense**
A dynamic real-time dashboard that delivers:

- Narrative Grouping – Clusters individual rumors into evolving crisis narratives  
- Threat Ranking – Severity labeling (Catastrophic Emergency, Lethal Misinformation)  
- Transparent Trust Architecture – 0–100 confidence scoring with reasoning traces  
- Instant Browser Alerts – Notifications when lethal hoaxes are confirmed  

---

## **⚙️ Technical Stack**

| Component      | Technology                     | Role |
|----------------|--------------------------------|------|
| Backend API    | Python, FastAPI                | High-performance async API |
| Database       | PostgreSQL (AsyncPG)           | Narrative & timeline storage |
| Agent Core     | Gemini 2.5 Flash, LangGraph    | AI orchestration & reasoning |
| Data Intake    | duckduckgo-search, feedparser, aiohttp | API-free autonomous ingestion |
| ORM            | SQLAlchemy (Async)             | Data modeling & CRUD |
| Frontend UI    | Vanilla JavaScript, HTML, Tailwind CSS | Lightweight real-time dashboard |

---

## **🚀 How to Run the Project**

### **Prerequisites**
- Python 3.10+  
- PostgreSQL database (Supabase, Neon, Railway recommended)  
- Gemini API Key  

---

### **1. Configure the Backend**

Navigate to:

backend-sentinel-ai/

Create a `.env` file:

```env
DATABASE_URL="postgresql+asyncpg://<USER>:<PASSWORD>@<HOST>:<PORT>/<DB_NAME>"
GEMINI_API_KEY="AIzaSy<YOUR_API_KEY>"

Install dependencies:

cd backend-sentinel-ai
pip install -r requirements.txt

2. Reset & Seed the Database

python reset_and_seed.py

3. Start the Backend Service
uvicorn app.main:app --reload


API URL:
http://localhost:8000/api/v1


4. Run the Frontend UI
Sentinel-AI/frontend-veritas-app/index.html

The dashboard will automatically begin populating with verified threats once the backend is running.

# Agency AI Orchestrator

AI-powered workflow automation for web agency tasks. Converts client requests into structured ClickUp tasks with technical plans, checklists, and QA approval.

## 🚀 Features

- **Google Form Integration**: Accept client requests via form submissions
- **ClickUp Lookup**: Automatically enriches tasks with client context (tech stack, brand guidelines)
- **Website Scraping**: Scrapes client website structure to inform technical plans
- **File Processing**: Extracts content from Google Drive attachments
- **Request Pre-Check**: AI classifier validates request completeness before planning — incomplete requests get routed to admin review instead of wasting architect tokens
- **AI Architect**: Generates detailed technical implementation plans using Claude (structured Pydantic output)
- **QA Review**: Automated quality checks with self-correction loop (up to 3 iterations)
- **Structured Output**: Creates ClickUp tasks with markdown descriptions, checklists, tags, and attachments
- **Langfuse Observability**: Full tracing, prompt management, and cost tracking

## 📋 Prerequisites

- Python 3.12+
- ClickUp API key
- Anthropic API key
- Langfuse instance (self-hosted or cloud) with prompts: `architect-agent`, `qa-review-agent`, `request-validator-classifier`
- ClickUp workspace with:
  - **Clients** space → **Active** folder → **Site Parameters** list
  - **Virtual Assistants** space → **Active** folder → **Dinesh - Upwork** list
  - **Theo** list (for admin review of incomplete requests)

## 🔧 Local Development

### 1. Clone and Install
```bash
cd theoruby.com
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### 2. Configure Environment
Create `.env` file:
```bash
ANTHROPIC_API_KEY=sk-ant-...
CLICKUP_API_KEY=pk_...
CLICKUP_TEAM_ID=...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://your-langfuse-instance.com
```

### 3. Run Demo
```bash
python3 demo_workflow.py
```

### 4. Start API Server
```bash
uvicorn app.main:app --reload
```

## 🌐 Deployment Options

### Option 1: Render.com (Recommended - Free)

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   gh repo create --public --source=. --remote=origin
   git push -u origin main
   ```

2. **Deploy on Render**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - Render auto-detects `render.yaml`
   - Add environment variables in dashboard:
     - `ANTHROPIC_API_KEY`
     - `CLICKUP_API_KEY`
     - `CLICKUP_TEAM_ID`
   - Click "Create Web Service"

3. **Your API will be live at**: `https://your-service-name.onrender.com`

**Free Tier Limitations:**
- Sleeps after 15 min inactivity (15-30s cold start)
- 512MB RAM
- Public repos only (or paid plan)

---

### Option 2: Railway.app

1. **Install Railway CLI**
   ```bash
   npm i -g @railway/cli
   railway login
   ```

2. **Deploy**
   ```bash
   railway init
   railway up
   ```

3. **Set Environment Variables**
   ```bash
   railway variables set ANTHROPIC_API_KEY=sk-ant-...
   railway variables set CLICKUP_API_KEY=pk_...
   railway variables set CLICKUP_TEAM_ID=...
   ```

4. **Generate Domain**
   ```bash
   railway domain
   ```

**Free Tier:** $5 credit/month, then usage-based

---

### Option 3: Fly.io (Always-On Free Tier)

1. **Install Fly CLI**
   ```bash
   curl -L https://fly.io/install.sh | sh
   fly auth signup
   ```

2. **Initialize**
   ```bash
   fly launch
   # Select region, say yes to Dockerfile generation
   ```

3. **Set Secrets**
   ```bash
   fly secrets set ANTHROPIC_API_KEY=sk-ant-...
   fly secrets set CLICKUP_API_KEY=pk_...
   fly secrets set CLICKUP_TEAM_ID=...
   ```

4. **Deploy**
   ```bash
   fly deploy
   ```

**Free Tier:** 3 shared VMs (256MB each), no sleep

---

## 🔗 Google Form Integration

### Webhook Setup

1. Deploy your app to one of the platforms above
2. Note your public URL: `https://your-app.onrender.com`
3. Create Google Form with fields:
   - Client ID (short text)
   - Client Request (paragraph)
   - Category (dropdown)
   - Priority (dropdown)

4. **Set up Google Apps Script**:
   - Form → 3 dots → Script editor
   - Paste:
   ```javascript
   function onFormSubmit(e) {
     var formData = {
       "Client ID": e.values[1],
       "Client Request": e.values[2],
       "Category": e.values[3],
       "Priority": e.values[4],
       "Timestamp": new Date().toISOString()
     };
     
     UrlFetchApp.fetch("https://your-app.onrender.com/webhook", {
       method: "post",
       contentType: "application/json",
       payload: JSON.stringify(formData)
     });
   }
   ```
   - Save & create trigger: onFormSubmit → Form submit

## 📊 Testing

### Graph Verification (mocked, no API keys needed)
```bash
python verification.py
```
Tests both routing branches: complete requests flow through architect/QA/push, incomplete requests route to admin task.

### Request Validator (live, needs Anthropic + Langfuse keys)
```bash
python test_request_validator.py
```

### Evaluator (live, needs Langfuse keys)
```bash
python test_evaluator.py
```

### API Test
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "thebusinessbeanstalk.co.uk",
    "request_text": "Add a contact form to the About page"
  }'
```

## 📁 Project Structure

```
theoruby.com/
├── app/
│   ├── main.py                    # FastAPI app
│   ├── graph.py                   # LangGraph orchestration (nodes, routing, graph)
│   ├── state.py                   # AgentState TypedDict + WebhookPayload
│   ├── _compat.py                 # Pydantic v1 compatibility patch for Python 3.14
│   ├── agents/
│   │   ├── architect.py           # Plan generation (structured TaskPlan output)
│   │   ├── review.py              # QA review
│   │   └── request_validator.py   # Request classification & completeness check
│   ├── domain/
│   │   ├── evaluator.py           # Lightweight non-LLM validation + cost tracking
│   │   ├── prompt_manager.py      # Langfuse prompt fetching & caching
│   │   └── request_category.py    # Request category constants
│   └── services/
│       ├── clickup.py             # ClickUp API client
│       ├── google_drive.py        # Google Drive file processing
│       ├── mock_google_drive.py   # Mock Drive service for local dev
│       └── web_scraper.py         # Website structure scraper
├── verification.py                # Graph integration test (both routing branches)
├── test_request_validator.py      # Request validator live tests
├── test_evaluator.py              # Evaluator live tests
├── requirements.txt
├── render.yaml
└── Procfile
```

## 🛠 Troubleshooting

### Task Description Empty in ClickUp?
- Check logs: `workflow_log_*.json`
- Ensure `ANTHROPIC_API_KEY` is set correctly
- Verify ClickUp accepts markdown in `description` field

### Cold Start Timeout on Render?
- Upgrade to paid tier ($7/month) for always-on
- Or switch to Fly.io free tier (no sleep)

### API Rate Limits?
- Claude Haiku: 50 requests/min (free tier)
- ClickUp: 100 requests/min

## 📝 License

MIT
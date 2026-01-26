# Agency AI Orchestrator

AI-powered workflow automation for web agency tasks. Converts client requests into structured ClickUp tasks with technical plans, checklists, and QA approval.

## 🚀 Features

- **Google Form Integration**: Accept client requests via form submissions
- **ClickUp Lookup**: Automatically enriches tasks with client context (tech stack, brand guidelines)
- **AI Architect**: Generates detailed technical implementation plans using Claude
- **QA Review**: Automated quality checks before task creation
- **Structured Output**: Creates ClickUp tasks with markdown descriptions, checklists, and tags

## 📋 Prerequisites

- Python 3.11+
- ClickUp API key
- Anthropic API key
- ClickUp workspace with:
  - **Clients** space → **Active** folder → **Site Parameters** list
  - **Virtual Assistants** space → **Active** folder → **Dinesh - Upwork** list

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
```

### 3. Run Demo
```bash
python demo_workflow.py
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

### Manual Test (Local)
```bash
python demo_workflow.py
```

### API Test
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "Client ID": "thebusinessbeanstalk.co.uk",
    "Client Request": "Add a contact form to the About page"
  }'
```

### Cleanup Test Task
```bash
curl -X DELETE https://api.clickup.com/api/v2/task/TASK_ID \
  -H "Authorization: YOUR_CLICKUP_API_KEY"
```

## 📁 Project Structure

```
theoruby.com/
├── app/
│   ├── main.py           # FastAPI app
│   ├── graph.py          # LangGraph orchestration
│   ├── state.py          # State management
│   ├── agents/
│   │   ├── architect.py  # Plan generation
│   │   └── review.py     # QA review
│   └── services/
│       └── clickup.py    # ClickUp API client
├── demo_workflow.py      # Test script
├── requirements.txt      # Dependencies
├── render.yaml          # Render config
└── Procfile             # Railway/Heroku config
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
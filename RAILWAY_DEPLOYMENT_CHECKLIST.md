# Railway Deployment Checklist

## Pre-Deployment

- [x] Code committed and pushed to main
- [x] All enrichment features implemented
- [x] Unit tests passing (25/25)
- [x] URL normalization added

## Railway Configuration

### 1. Build Settings

Railway auto-detects:
- ✅ Python project (via `pyproject.toml`)
- ✅ Poetry for dependency management
- ✅ Build command: `poetry install`
- ✅ Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

**No manual configuration needed!** Railway will use Poetry automatically.

### 2. Required Environment Variables

Set these in Railway UI (Variables tab):

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Langfuse (already deployed on Railway)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://langfuse-web-production-6d35.up.railway.app

# ClickUp API
CLICKUP_API_KEY=pk_...
CLICKUP_SPACE_ID=...
CLICKUP_LIST_ID=...              # Main client list
THEO_LIST_ID=...                 # Theo's admin review list
SITE_PARAMETERS_LIST_ID=...      # Client website parameters

# Google Drive (for file processing)
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}
```

### 3. Optional Environment Variables

**These have defaults in code - only set if you want different values:**

```bash
# Enrichment Configuration (defaults work well)
ENRICHMENT_MAX_ITERATIONS=3              # Default: 3
ENRICHMENT_MAX_TOKENS=500000             # Default: 500,000
ENRICHMENT_TOOL_TIMEOUT=30               # Default: 30 seconds

# Real API Keys (optional - currently using mocks)
SERPER_API_KEY=...                       # For web_search tool
GOOGLE_MAPS_API_KEY=...                  # For google_maps/reviews tools
```

**Recommendation**: Skip optional vars for initial deployment, add later if needed.

---

## Deployment Steps

### Step 1: Verify GitHub Connection

1. Go to Railway dashboard
2. Check that repo is connected: `tinsilver/agency-ai-orchestrator`
3. Verify auto-deploy is enabled for `main` branch

### Step 2: Set Environment Variables

1. Railway Dashboard → Your Project → Variables tab
2. Click "+ New Variable"
3. Add each required variable from section 2 above
4. **Important**: Don't add quotes around JSON values
5. Click "Deploy" after adding all variables

### Step 3: Verify Deployment

Railway will automatically:
1. Detect `pyproject.toml`
2. Run `poetry install` (installs all dependencies)
3. Start with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Expose on public URL

**Watch deployment logs**:
- Railway Dashboard → Deployments → Latest deployment
- Look for: "Application startup complete" or similar
- Check for errors in red

### Step 4: Test Deployment

**Option A: Use test script**

```bash
./test_railway_deployment.sh https://your-app.up.railway.app
```

**Option B: Manual tests**

```bash
# 1. Health check
curl https://your-app.up.railway.app/health

# 2. Test enrichment workflow
curl -X POST https://your-app.up.railway.app/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "theoruby.com",
    "raw_request": "Add a contact form",
    "form_source": "test",
    "priority": 2
  }'
```

### Step 5: Verify in Langfuse

1. Go to: https://langfuse-web-production-6d35.up.railway.app
2. Navigate to Traces
3. Look for new trace from webhook
4. Check enrichment metrics:
   - `enrichment_iterations`
   - `enrichment_success`
   - `enrichment_stop_reason`
   - Tool usage metrics

### Step 6: Test from Google Form

1. Submit a test request via your Google Form
2. Check ClickUp for new task
3. Verify enrichment ran (check Langfuse trace)
4. Confirm task has correct information

---

## Troubleshooting

### Deployment Failed

**Check Railway logs**:
```
Railway Dashboard → Deployments → Failed deployment → View logs
```

**Common issues**:

1. **Missing environment variable**
   - Error: `KeyError: 'ANTHROPIC_API_KEY'`
   - Fix: Add the missing variable in Railway UI

2. **Pydantic v1 compatibility issue**
   - Error: `AttributeError: 'function' object has no attribute '__annotations__'`
   - Fix: Verify `app/_compat.py` is present and imported first in `app/__init__.py`

3. **Port binding issue**
   - Error: `Address already in use`
   - Fix: Ensure start command uses `--port $PORT` (Railway provides this)

4. **Langfuse connection failure**
   - Error: `Connection refused` or timeout
   - Fix: Check `LANGFUSE_BASE_URL` is correct (https, not http)

### Enrichment Not Running

**Check Langfuse traces**:
1. Look for `dynamic-enrichment-node` spans
2. If missing, check if validation is passing on first try
3. Review validator prompt thresholds

**Check logs for errors**:
```bash
# Railway Dashboard → View Logs
# Look for errors like:
# - "Could not find Client Task"
# - "Request URL is missing protocol"
# - "Tool budget exceeded"
```

### Tools Returning Errors

**URL errors**:
- ✅ Fixed: URL normalization now adds `https://` automatically
- Verify client_id format in webhook payload

**API key errors**:
- Check optional API keys (SERPER_API_KEY, GOOGLE_MAPS_API_KEY)
- Tools will use mocks if API keys not set (expected behavior)

---

## Post-Deployment

### Monitor for 24 Hours

**Check every few hours**:
- [ ] Railway deployment status (green)
- [ ] Langfuse trace volume (requests coming in)
- [ ] ClickUp tasks being created
- [ ] Error rate in Railway logs

### Review Metrics (After 1 Week)

**In Langfuse dashboard, analyze**:
1. **Enrichment Success Rate**
   - Target: 60%+ of incomplete requests become complete
   - Metric: `enrichment_success`

2. **Answer Rate**
   - Target: 40%+ on factual questions
   - Metric: `enrichment_answer_rate`

3. **Average Iterations**
   - Target: 1.5-2 iterations average
   - Metric: `enrichment_iterations`

4. **Token Usage**
   - Target: < 150K tokens average per request
   - Metric: `enrichment_total_tokens`

5. **Stop Reasons**
   - `complete`: Good! (target: 60%+)
   - `max_iterations`: Neutral (target: 30%)
   - `no_progress`: Bad if high (target: < 10%)
   - `token_limit`: Bad if any (target: 0%)

### Tune Prompts Based on Results

**If success rate is low (< 40%)**:
1. Lower validation thresholds in `request-validator-classifier`
2. Make planner more aggressive with tool usage
3. Add more tool budget

**If token usage is high (> 200K)**:
1. Reduce tool budgets for expensive tools
2. Simplify prompt language
3. Truncate tool outputs

**If no_progress rate is high (> 20%)**:
1. Improve tool selection in planner prompt
2. Add better tool-specific answer extraction
3. Consider adding more tools

---

## Rollback Plan

If deployment causes issues:

### Option 1: Revert to Previous Deployment

```bash
# Railway Dashboard → Deployments → Select working deployment → Redeploy
```

### Option 2: Revert Git Commit

```bash
# Find last working commit
git log --oneline

# Revert to it
git revert HEAD
git push origin main

# Railway will auto-deploy the revert
```

### Option 3: Disable Enrichment Temporarily

Set environment variable in Railway:
```bash
ENRICHMENT_MAX_ITERATIONS=0
```

This will skip enrichment and route directly to admin tasks (old behavior).

---

## Success Criteria

Deployment is successful when:

- [x] Railway build completes without errors
- [x] Application starts and serves requests
- [x] Health endpoint returns 200 OK
- [x] Test webhook creates ClickUp task
- [x] Langfuse shows trace with enrichment spans
- [x] No critical errors in Railway logs
- [ ] Real form submission works end-to-end
- [ ] Enrichment metrics appear in Langfuse

---

## Notes

### Poetry on Railway

✅ **Fully Supported**
- Railway detects `pyproject.toml` automatically
- Runs `poetry install` during build
- Uses `poetry.lock` for reproducible builds
- No need to generate `requirements.txt`

### New Files Deployed

The enrichment system added these files (all included in deployment):

**New Services**:
- `app/services/enrichment_toolkit.py`
- `app/services/web_search.py`
- `app/services/form_detector.py`
- `app/services/social_media_finder.py`
- `app/services/seo_audit.py`
- `app/services/image_analysis.py`
- `app/services/pdf_extractor.py`
- `app/services/google_maps_scraper.py`
- `app/services/google_reviews_scraper.py`

**New Agents**:
- `app/agents/dynamic_enrichment.py`

**New Models**:
- `app/domain/enrichment_models.py`

**Modified Core Files**:
- `app/graph.py` (enrichment loop, routing)
- `app/state.py` (8 new fields)
- `app/main.py` (enrichment initialization)
- `app/agents/architect.py` (enrichment context)
- `app/domain/evaluator.py` (enrichment metrics)

### Dependencies Added

Check `pyproject.toml` for new dependencies:
- `beautifulsoup4` - HTML parsing for tools
- `pypdf` - PDF text extraction
- All others already present

---

**Last Updated**: 2026-02-23
**Deployment Ready**: ✅ YES

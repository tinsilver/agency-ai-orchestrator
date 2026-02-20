# Enrichment System Deployment Guide

## Overview

This guide covers deploying and operating the recursive context-gathering validation system (enrichment workflow) in production.

**System Purpose**: Automatically gather missing information about incomplete client requests using 9 specialized tools, improving the AI automation's success rate by reducing the need for manual follow-ups.

---

## Architecture Quick Reference

```
Webhook Request
    ↓
static_enrichment (ClickUp + website)
    ↓
file_processing (Google Drive)
    ↓
validate_request ←─────────┐
    ↓                      │
    ├─ complete? → architect
    ├─ exhausted? → create_admin_task
    └─ continue? → dynamic_enrichment ─┘
                   (max 3 iterations)
```

---

## Prerequisites

### Required
- Python 3.14+ (with pydantic v1 compatibility patch)
- FastAPI + Uvicorn
- LangGraph + LangChain
- Langfuse (self-hosted or cloud)
- Claude Haiku 4.5 API access (via Anthropic)

### Optional (for real tool implementations)
- Google Maps API key (for google_maps_scraper, google_reviews_scraper)
- Serper API key or similar (for web_search)
- pypdf library (for pdf_extract)

### Current Implementation Status
- ✅ Core workflow and routing logic
- ✅ All 9 tool services (some mocked)
- ✅ DynamicEnrichmentAgent
- ✅ State management and budget enforcement
- ✅ Langfuse observability integration
- ⏳ Langfuse prompts (need to be created manually)
- ⏳ Real API integrations (currently mocked: web_search, google_maps, google_reviews)

---

## Installation

### 1. Dependencies

Ensure `pyproject.toml` includes:

```toml
[tool.poetry.dependencies]
python = "^3.14"
langchain = "^0.3.16"
langchain-anthropic = "^0.3.4"
langchain-community = "^0.3.15"
langgraph = "^0.2.64"
langfuse = "^3.0.0"
fastapi = "^0.115.12"
uvicorn = "^0.34.0"
pydantic = "^2.10.6"
beautifulsoup4 = "^4.12.3"
requests = "^2.32.3"
pypdf = "^5.1.0"  # For PDF extraction
```

Install:
```bash
poetry install
```

### 2. Environment Variables

Create or update `.env`:

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Langfuse (self-hosted or cloud)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://your-langfuse-instance.com

# ClickUp API
CLICKUP_API_KEY=pk_...
CLICKUP_SPACE_ID=...
CLICKUP_LIST_ID=...

# Google Drive (if using)
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}

# Optional: Real API integrations
SERPER_API_KEY=...  # For web_search
GOOGLE_MAPS_API_KEY=...  # For google_maps/reviews scrapers

# Enrichment Configuration (optional, defaults shown)
ENRICHMENT_MAX_ITERATIONS=3
ENRICHMENT_MAX_TOKENS=500000
ENRICHMENT_TOOL_TIMEOUT=30
```

### 3. Verify Installation

```bash
# Run unit tests
python -m pytest tests/test_enrichment_workflow.py -v

# Should see: 25 passed
```

---

## Langfuse Prompt Setup

The enrichment system requires **1 new prompt** and **modifications to 2 existing prompts**.

### Step 1: Create `dynamic-enrichment-planner` (NEW)

1. Go to Langfuse UI → Prompts → Create New Prompt
2. **Name**: `dynamic-enrichment-planner`
3. **Label**: `production`
4. **Model**: `claude-haiku-4-5-20251001`
5. **Type**: Chat (System + User messages)

**System Message**:
```
You are an intelligent context enrichment planner. Your job is to create a plan for gathering missing information about a client's web development request.

You have access to the following tools:
{{available_tools}}

## Your Task

Analyze the missing information questions and create a plan for which tools to use.

ORIGINAL REQUEST:
{{raw_request}}

STATIC CONTEXT:
{{static_context}}

WEBSITE URL:
{{website_url}}

MISSING INFORMATION (questions that need answers):
{{missing_information}}

## Tool Selection Guidelines

- **web_fetch**: Use when you need to inspect a specific page on the client's website (forms, structure, content)
- **web_search**: Use to find social media accounts, current SEO rankings, competitor information, or public business info
- **form_detector**: Use when questions mention forms, contact pages, or form fields
- **social_media_finder**: Use when questions ask about social media presence or links
- **seo_audit**: Use when questions relate to SEO, meta tags, keywords, or page optimization
- **image_analysis**: Use when questions involve images, dimensions, or visual content
- **pdf_extract**: Use for brand guidelines, color palettes, fonts, or specifications in PDFs
- **google_maps_scraper**: Use for business hours, location, address, or contact information
- **google_reviews_scraper**: Use for reputation, ratings, or customer feedback

## Important Rules

1. ONLY use tools that have remaining budget (calls > 0)
2. Do NOT use tools for questions that require client preference or subjective decisions
3. Be specific with parameters (URLs, queries, etc.)
4. Prioritize tools most likely to find factual answers
5. You can use multiple tools for the same question if needed
6. Do NOT invent information - only factual gathering

## Output Format

Return a JSON object with this structure:

{
  "actions": [
    {
      "tool": "tool_name",
      "question": "Which question this answers",
      "params": {"url": "https://...", "query": "...", etc},
      "reasoning": "Why this tool for this question"
    }
  ],
  "total_estimated_tokens": 1000,
  "reasoning": "Overall strategy for this enrichment attempt"
}

Create an efficient plan that maximizes information gathering within budget constraints.
```

**User Message**:
```
Create an enrichment plan for the above request.
```

**Output Schema**: Configure for structured output (if supported) or JSON mode

6. **Save** and set label to `production`

### Step 2: Update `request-validator-classifier` (MODIFY)

Edit the existing `request-validator-classifier` prompt:

1. Find the prompt in Langfuse UI
2. Add these variables to compilation (in your code):
   - `enrichment_iteration` (0, 1, 2, or 3)
   - `enrichment_context` (formatted dynamic context)
   - `enrichment_history` (list of previous attempts)

3. Add this section **after** the static context section in the prompt:

```
## Enrichment Context

ENRICHMENT ITERATION: {{enrichment_iteration}} of 3
{{enrichment_context}}

## Iteration-Aware Validation

Your validation standards should adjust based on the iteration:

- **Iteration 0** (first validation, no enrichment yet): Be **moderately strict** (confidence threshold: 0.85)
  - Pass only if request is very clear with sufficient detail
  - Ask for missing information that could be gathered through research or is subjective

- **Iteration 1** (after first enrichment): Be **moderately lenient** (confidence threshold: 0.75)
  - Consider what information was successfully gathered
  - Trust reasonable inferences from gathered context
  - Still require critical subjective information from client

- **Iteration 2** (after second enrichment): Be **lenient** (confidence threshold: 0.65)
  - Give benefit of the doubt if core functionality is clear
  - Accept reasonable defaults for minor details
  - Only require truly blocking information from client

- **Iteration 3** (after third enrichment): Be **very lenient** (confidence threshold: 0.60)
  - Pass if a competent developer could make reasonable decisions
  - Only block if fundamentally unclear or requires critical client preference

## Previous Enrichment Attempts

{{enrichment_history}}

Use this to understand what information gathering was already attempted and what was found/not found.
```

4. Update the "complete" field logic instructions:

```
The "complete" field should be:
- true: If request has enough detail given the current iteration
- false: If critical information is still missing after enrichment attempts

Remember: Each iteration makes more information available. Re-evaluate completeness with ALL context.
```

5. **Save** as new version with label `production`

### Step 3: Update `architect-agent` (MODIFY)

Edit the existing `architect-agent` prompt:

1. Find the prompt in Langfuse UI
2. Add this variable to compilation (in your code):
   - `enrichment_context` (will be auto-formatted by ArchitectAgent)

3. Add this placeholder **after** the website_context section:

```
{{enrichment_context}}
```

The `enrichment_context` variable is already formatted by the ArchitectAgent with:
- Header: "## 🔍 Additional Context from Enrichment"
- Bullet points of gathered information
- Source and confidence for each piece

4. **Save** as new version with label `production`

---

## Configuration

### Default Enrichment Settings

The system uses these defaults (can be overridden via environment variables):

```python
ENRICHMENT_CONFIG = {
    "max_iterations": 3,  # Maximum enrichment loop iterations
    "max_tokens": 500_000,  # Total token budget for all enrichments
    "tool_budgets": {
        "web_fetch": 5,
        "web_search": 3,
        "image_analysis": 3,
        "pdf_extract": 2,
        "form_detector": 3,
        "social_media_finder": 2,
        "seo_audit": 1,
        "google_maps_scraper": 1,
        "google_reviews_scraper": 1
    },
    "confidence_thresholds": {
        "iteration_0": 0.85,  # Strict (first validation)
        "iteration_1": 0.75,  # Moderate
        "iteration_2": 0.65,  # Lenient
        "iteration_3": 0.60   # Very lenient
    },
    "timeout_per_tool": 30  # seconds
}
```

### Adjusting Configuration

To change defaults, set environment variables:

```bash
# Increase max iterations (use with caution)
ENRICHMENT_MAX_ITERATIONS=4

# Increase token budget for complex requests
ENRICHMENT_MAX_TOKENS=750000

# Adjust tool budgets (JSON format)
ENRICHMENT_TOOL_BUDGETS='{"web_fetch": 10, "seo_audit": 2}'
```

Or modify in code:

```python
# app/main.py
input_state = {
    # ... other fields ...
    "enrichment_iteration": 0,
    "max_enrichment_tokens": 750_000,  # Increase budget
    # ...
}
```

---

## Running the System

### Local Development

```bash
# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# Send test webhook
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "test-client",
    "raw_request": "Add a contact form to the about page",
    "form_source": "test",
    "priority": 2
  }'
```

### Production Deployment

```bash
# Using Docker (recommended)
docker build -t enrichment-system .
docker run -p 8000:8000 --env-file .env enrichment-system

# Or using Railway/Heroku
railway up
# or
git push heroku main
```

### Monitoring Workflow

1. **Langfuse Dashboard**: Monitor traces in real-time
   - Navigate to: `https://your-langfuse-instance.com`
   - View traces for each workflow execution
   - Check enrichment metrics and tool usage

2. **Logs**: Check application logs for errors
   ```bash
   tail -f logs/app.log
   ```

3. **ClickUp**: Verify tasks are created correctly
   - Check that incomplete requests create admin tasks
   - Verify complete requests create technical spec tasks

---

## Enrichment Workflow Behavior

### Iteration Flow

**Iteration 0** (Initial Validation):
- Validator runs with no dynamic context
- Strict threshold (0.85 confidence required)
- If incomplete → routes to `dynamic_enrichment`

**Iteration 1** (After First Enrichment):
- Tools attempt to gather missing information
- dynamic_context populated with findings
- Validator re-runs with enriched context
- Moderate threshold (0.75 confidence)
- If still incomplete → routes to `dynamic_enrichment` again

**Iteration 2** (After Second Enrichment):
- More tools may be used (different from iteration 1)
- dynamic_context grows with new findings
- Validator re-runs with all context
- Lenient threshold (0.65 confidence)
- If still incomplete → routes to `dynamic_enrichment` one last time

**Iteration 3** (After Third Enrichment - Final):
- Last attempt to gather information
- Very lenient threshold (0.60 confidence)
- If still incomplete → routes to `create_admin_task` (exhausted)
- If complete → routes to `architect`

### Stopping Conditions

The enrichment loop stops when:

1. **✅ Complete**: Request passes validation
   - **Route**: `architect` → Creates technical spec
   - **Stop Reason**: `"complete"`

2. **🔴 Max Iterations**: 3 enrichment attempts exhausted
   - **Route**: `create_admin_task` → Manual review needed
   - **Stop Reason**: `"max_iterations"`

3. **🔴 Token Limit**: Exceeds 500K token budget
   - **Route**: `create_admin_task`
   - **Stop Reason**: `"token_limit"`

4. **🔴 No Progress**: Same questions remain across iterations
   - **Route**: `create_admin_task`
   - **Stop Reason**: `"no_progress"`

---

## Observability

### Langfuse Metrics

The system reports these metrics for each workflow execution:

**Enrichment Metrics**:
- `enrichment_iterations` (NUMERIC) - Number of enrichment attempts (0-3)
- `enrichment_success` (BOOLEAN) - Did enrichment make request complete?
- `enrichment_stop_reason` (CATEGORICAL) - Why enrichment stopped
- `enrichment_total_tokens` (NUMERIC) - Total tokens used for enrichment
- `enrichment_answer_rate` (NUMERIC) - % of questions answered by tools

**Tool Usage Metrics** (per tool):
- `tool_web_fetch_calls` (NUMERIC)
- `tool_web_search_calls` (NUMERIC)
- `tool_seo_audit_calls` (NUMERIC)
- ... (one for each tool)

**Quality Metrics**:
- `questions_initially_missing` (NUMERIC)
- `questions_answered_by_enrichment` (NUMERIC)
- `final_enrichment_confidence` (NUMERIC) - Average confidence of gathered info

### Viewing Traces

1. Navigate to Langfuse dashboard
2. Go to **Traces** tab
3. Look for traces with name: `workflow-execution`
4. Expand to see:
   - `static-enrichment-node`
   - `file-processing-node`
   - `validate-request-node` (may appear multiple times)
   - `dynamic-enrichment-node` (1-3 times)
   - `architect-node` or `create-admin-task-node`

Each `dynamic-enrichment-node` contains:
- `dynamic-enrichment-agent` span
  - `create-enrichment-plan` (LLM call)
  - `web-fetch-tool`, `seo-audit-tool`, etc. (tool calls)
  - Token counts and timing

### Key Performance Indicators

**Target Metrics** (from feature requirements):
- **80%+** of incomplete requests should become complete after enrichment
- **60%+** answer rate on factual questions
- Average **1.5-2 iterations** per request
- **< 100K tokens** average per request

**Red Flags**:
- 🚩 > 2.5 average iterations (prompts may be too strict)
- 🚩 < 30% answer rate (tools not being used effectively)
- 🚩 > 50% "no_progress" stop reasons (tools can't find info)
- 🚩 > 200K average tokens (prompts too verbose or loops inefficient)

---

## Troubleshooting

### Issue: Enrichment loop runs but doesn't find information

**Symptoms**:
- `enrichment_answer_rate` is very low (< 20%)
- Tools are being called but returning empty results
- Stop reason is often `"no_progress"`

**Possible Causes**:
1. Website URL is incorrect or inaccessible
2. Mock tools are being used instead of real APIs
3. Enrichment planner is choosing wrong tools for questions
4. Questions are too subjective to be answered by tools

**Solutions**:
- Verify website URL is correct in ClickUp client context
- Check if real API keys are configured (SERPER_API_KEY, GOOGLE_MAPS_API_KEY)
- Review `dynamic-enrichment-planner` prompt - may need tuning
- Check Langfuse traces to see which tools were attempted and their results

### Issue: Token budget exceeded frequently

**Symptoms**:
- `enrichment_stop_reason` is often `"token_limit"`
- `enrichment_total_tokens` is consistently near 500K

**Possible Causes**:
1. Prompts are too verbose
2. Tools returning very large results (e.g., full webpage HTML)
3. Too many tool calls per iteration

**Solutions**:
- Increase `ENRICHMENT_MAX_TOKENS` if budget is too strict
- Reduce `tool_budgets` for expensive tools (seo_audit, web_fetch)
- Optimize tool services to return summarized data, not raw HTML
- Review prompts for unnecessary verbosity

### Issue: Requests still incomplete after 3 iterations

**Symptoms**:
- `enrichment_success` is False
- `enrichment_stop_reason` is `"max_iterations"`
- Admin tasks are being created frequently

**Possible Causes**:
1. Validation thresholds are too strict
2. Questions are inherently subjective (need client input)
3. Tools can't access required information

**Solutions**:
- Review `confidence_thresholds` in configuration - consider lowering
- Check if missing questions are factual or subjective
- Update `request-validator-classifier` prompt to be more lenient at iteration 3
- Some requests legitimately need client clarification - this is expected

### Issue: Enrichment not running at all

**Symptoms**:
- No `dynamic-enrichment-node` spans in traces
- Workflow goes straight from `validate_request` to `architect` or `create_admin_task`

**Possible Causes**:
1. Requests are passing validation on first try (good!)
2. Routing logic is broken
3. enrichment_iteration is not being initialized

**Solutions**:
- Check if requests are actually complete (may not need enrichment)
- Verify `route_after_validation_with_enrichment` logic in graph.py
- Ensure `enrichment_iteration` starts at 0 in main.py input_state
- Run unit tests: `pytest tests/test_enrichment_workflow.py`

### Issue: Tools timing out

**Symptoms**:
- Tool results show `{"error": "timeout"}`
- Traces show long execution times for tool spans

**Possible Causes**:
1. External APIs are slow or unresponsive
2. Timeout setting is too strict (default: 30s)
3. Network issues

**Solutions**:
- Increase `ENRICHMENT_TOOL_TIMEOUT` environment variable
- Implement retry logic in tool services
- Add circuit breakers for unreliable APIs
- Use mock tools for development/testing

---

## Maintenance

### Regular Tasks

**Daily**:
- Monitor Langfuse dashboard for errors
- Check enrichment success rate metrics
- Review admin tasks created (indicates enrichment failures)

**Weekly**:
- Analyze tool usage patterns - are all tools being used effectively?
- Review average iterations per request
- Check token usage trends

**Monthly**:
- Tune prompts based on real-world performance
- Adjust confidence thresholds if needed
- Update tool budgets based on usage patterns
- Review and optimize expensive tools

### Prompt Tuning

When tuning prompts based on metrics:

1. **If answer rate is low (< 40%)**:
   - Make `dynamic-enrichment-planner` more aggressive with tool usage
   - Ensure tool selection guidelines match actual questions

2. **If success rate is low (< 60%)**:
   - Lower confidence thresholds in `request-validator-classifier`
   - Make validator more lenient at higher iterations

3. **If token usage is high (> 150K average)**:
   - Simplify prompt language
   - Reduce tool output verbosity
   - Limit number of tools per iteration

---

## Upgrading Tools from Mock to Real

Several tools currently use mock implementations. Here's how to upgrade:

### web_search Service

```python
# app/services/web_search.py

# Add to __init__
self.serper_api_key = os.getenv("SERPER_API_KEY")

# Replace _mock_search with:
async def search(self, query: str, num_results: int = 5) -> Dict[str, Any]:
    if not self.serper_api_key:
        return self._mock_search(query, num_results)

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": self.serper_api_key},
                json={"q": query, "num": num_results}
            )
            data = response.json()

            return {
                "query": query,
                "results": [
                    {"title": r["title"], "url": r["link"], "snippet": r["snippet"]}
                    for r in data.get("organic", [])
                ],
                "is_mock": False
            }
    except Exception as e:
        return {"error": f"Web search failed: {str(e)}"}
```

### google_maps_scraper Service

Similar pattern - add Google Places API integration:

```python
# app/services/google_maps_scraper.py

# Use googlemaps library
import googlemaps
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
# ... follow commented example in file
```

### google_reviews_scraper Service

Same as google_maps_scraper - use Google Places API for reviews.

---

## Security Considerations

1. **API Keys**: Never commit API keys to version control
   - Use environment variables
   - Rotate keys regularly
   - Use separate keys for dev/staging/production

2. **Rate Limiting**: Implement rate limits to prevent abuse
   - Tool budgets provide first line of defense
   - Add API-level rate limiting for webhooks

3. **Data Privacy**: Be mindful of client data
   - Langfuse traces may contain sensitive information
   - Configure data retention policies
   - Comply with GDPR/privacy regulations

4. **Validation**: Always validate webhook inputs
   - Check client_id exists in ClickUp
   - Sanitize URLs before fetching
   - Validate file attachments

---

## Support and Documentation

### Resources
- **Langfuse Prompts Guide**: `LANGFUSE_PROMPTS_GUIDE.md`
- **Test Plan**: `ENRICHMENT_TEST_PLAN.md`
- **Test Results**: `ENRICHMENT_TEST_RESULTS.md`
- **Feature Spec**: `FEATURE-improve-validator.md`
- **Example Requests**: `Example client requests.md`

### Getting Help
1. Check Langfuse traces for detailed execution logs
2. Run unit tests to verify core logic: `pytest tests/test_enrichment_workflow.py`
3. Review this deployment guide
4. Check logs for error messages

---

## Success Checklist

Before going to production:

- [ ] All environment variables configured
- [ ] Langfuse prompts created (`dynamic-enrichment-planner`)
- [ ] Existing prompts updated (validator, architect)
- [ ] Unit tests passing (25/25)
- [ ] Real API keys configured (at minimum: Anthropic, Langfuse, ClickUp)
- [ ] Tested with sample requests from `Example client requests.md`
- [ ] Langfuse dashboard accessible and showing traces
- [ ] Monitoring and alerting configured
- [ ] Documentation reviewed by team

---

## Appendix: State Schema Reference

```python
class AgentState(TypedDict):
    # ... existing fields ...

    # Enrichment tracking
    enrichment_iteration: int  # 0-3, tracks enrichment loop count
    enrichment_history: Optional[List[Dict[str, Any]]]  # History of attempts
    dynamic_context: Optional[Dict[str, Any]]  # Context gathered by tools
    tool_usage_stats: Optional[Dict[str, Any]]  # Track tool calls
    total_enrichment_tokens: int  # Running token count
    max_enrichment_tokens: int  # Budget (default 500K)
    enrichment_complete: Optional[bool]  # True if succeeded/exhausted
    enrichment_stop_reason: Optional[str]  # "complete"|"max_iterations"|"no_progress"|"token_limit"
```

---

**Last Updated**: 2026-02-20
**Version**: 1.0
**Status**: Ready for Production (pending Langfuse prompt creation)

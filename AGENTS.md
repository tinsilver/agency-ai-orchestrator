# Environment

Use `python3` and `pip3` to run the code.

Clickup.com API documentation is here: https://developer.clickup.com/reference/
Langfuse documentation is here: https://langfuse.com/docs/

# Agency AI Orchestrator: System Design

## 1. Logic Flow

The system operates as a LangGraph StateGraph with conditional routing and a QA self-correction loop.

```
enrichment -> file_processing -> validate_request --[complete]--> architect -> qa_reviewer -> push_to_clickup -> END
                                                  --[incomplete]--> create_admin_task -> END
```

- **Enrichment** fetches client context from ClickUp (Site Parameters list) and scrapes the client website.
- **File Processing** extracts content from Google Drive attachments (or uses mock service).
- **Request Validation** classifies the request by category and checks completeness. Incomplete/unclear requests are routed to an admin review task instead of the architect.
- **Architect + QA loop** generates a technical plan and reviews it (up to 3 iterations).
- **ClickUp Push** creates the final task with markdown description, checklist, tags, and attachments.

## 2. Agent Roles

- **Request Validator** (`app/agents/request_validator.py`): Classifies requests into one of 10 categories (see `app/domain/request_category.py`) and evaluates completeness. Uses structured output (`ClassificationResult`) to return category, subcategories, completeness flag, missing information, confidence, and reasoning. Incomplete requests are routed to Theo's ClickUp list for manual clarification.
- **Architect** (`app/agents/architect.py`): The "Technical Writer." Converts complete client requests into dev-ready tasks using a strict Pydantic schema (`TaskPlan`) with task name, markdown description, checklist, and tags.
- **QA Reviewer** (`app/agents/review.py`): The "Gatekeeper." Reviews the architect's plan against the original request. Returns `APPROVE` or a critique that triggers re-generation.

All agents use `ChatAnthropic` (Claude Haiku 4.5), prompts managed via Langfuse (`PromptManager`), and `@observe()` decorators for tracing.

## 3. Request Categories

Defined in `app/domain/request_category.py`:

| Category | Description |
|---|---|
| `blog_post` | Writing blog content, articles |
| `seo_optimization` | SEO improvements, keyword targeting, meta tags |
| `bug_fix` | Fixing something broken or not working |
| `content_update` | Updating existing text, images, or media |
| `business_info_update` | Changing hours, address, phone, staff info |
| `new_page` | Creating an entirely new page |
| `form_changes` | Modifying forms (contact, booking, etc.) |
| `design_changes` | Visual/UI changes, layout, styling |
| `feature_request` | Adding new functionality |
| `unclear` | Cannot determine what is being requested |

## 4. State Management

`AgentState` (TypedDict) tracks:

- **Input**: `client_id`, `raw_request`, `attached_files`
- **Enrichment**: `client_context`, `website_content`, `file_summaries`
- **Classification**: `request_category`, `request_subcategories`, `is_request_complete`, `missing_information`, `needs_admin_review`
- **Planning**: `task_md`, `critique`, `iterations`
- **Output**: `admin_task_id` (for incomplete requests), `history`, `logs`

## 5. Observability

- **Langfuse** (self-hosted) provides tracing for all graph nodes and agent calls
- `LightweightValidator` runs non-LLM checks (request length, action verbs, greeting detection, plan structure) and reports scores to traces
- Token usage and cost are tracked per agent call via `report_usage()`
- Prompts are version-controlled in Langfuse with `production` labels

## 6. ClickUp Lists

| List | ID | Purpose |
|---|---|---|
| Site Parameters | `901520311911` | Client context lookup |
| Dinesh - Upwork | `901520311855` | Complete tasks for dev work |
| Theo | `901520364480` | Incomplete requests for admin review |
from typing import Literal, Optional
import os
import requests
from langgraph.graph import StateGraph, END
from langfuse import observe, get_client

from app.state import AgentState
from app.services.clickup import ClickUpService
from app.services.web_scraper import WebScraperService
from app.agents.architect import ArchitectAgent
from app.agents.review import ReviewAgent
from app.agents.request_validator import RequestValidatorAgent
from app.domain.evaluator import LightweightValidator

# File processing service (use mock if no Google Drive credentials)
USE_REAL_DRIVE = bool(os.getenv("GOOGLE_DRIVE_CREDENTIALS"))
if USE_REAL_DRIVE:
    from app.services.google_drive import GoogleDriveService
    drive_service = GoogleDriveService()
else:
    from app.services.mock_google_drive import MockGoogleDriveService
    drive_service = MockGoogleDriveService()

# Initialize Services & Agents
clickup_service = ClickUpService()
web_scraper = WebScraperService()
architect_agent = ArchitectAgent()
review_agent = ReviewAgent()
request_validator = RequestValidatorAgent()
validator = LightweightValidator()

# --- Node Definitions ---

# List IDs from discovery
SITE_PARAMETERS_LIST_ID = "901520311911"
DINESH_UPWORK_LIST_ID = "901520311855"
THEO_LIST_ID = "901520364480"

def map_priority_to_clickup(priority_str: str) -> Optional[int]:
    """
    Map semantic priority strings to ClickUp API integer values.

    ClickUp API:
    - 1 = urgent
    - 2 = high
    - 3 = normal
    - 4 = low
    - None = no priority set
    """
    mapping = {
        "urgent": 1,
        "high": 2,
        "normal": 3,
        "low": 4,
    }
    return mapping.get(priority_str.lower()) if priority_str else None

@observe(name="enrichment-node")
async def enrichment_node(state: AgentState):
    """Fetch client data from ClickUp Task and scrape website."""
    client_name = state["client_id"] # Matches "Client ID" from form, e.g. domain name
    history = state.get("history", [])
    website_content = None
    
    # 1. ClickUp Enrichment
    # Find the task in "Site Parameters" list that matches the client name
    tasks = await clickup_service.get_tasks(SITE_PARAMETERS_LIST_ID)
    target_task = next((t for t in tasks if t["name"] == client_name), None)
    
    context = {}

    if target_task:
        task_id = target_task["id"]
        # 2. Get details (custom fields)
        task_data = await clickup_service.get_task_details(task_id)
        
        if task_data:
            context["Client Name"] = task_data.get("name")
            # Extract custom fields into a flat dict
            for field in task_data.get("custom_fields", []):
                if "value" in field:
                    context[field["name"]] = field["value"]
            
            action = f"Enriched context from ClickUp Task '{client_name}' ({task_id})"
        else:
            action = f"Failed to get details for task {task_id}"
    else:
        action = f"Could not find Client Task '{client_name}' in Site Parameters"
        context["Note"] = "Context not found, using defaults if any"

    history.append(action)

    # 2. Website Scraping
    # If client_id looks like a domain, try to scrape it
    if "." in client_name and not " " in client_name:
        scrape_result = await web_scraper.scrape_url(client_name)
        if not scrape_result.get("error"):
            website_content = (
                f"Page Title: {scrape_result['title']}\n"
                f"Description: {scrape_result['description']}\n\n"
                f"--- Structure Summary ---\n{scrape_result['structure_summary']}\n\n"
                f"--- Detected Sections ---\n{', '.join(scrape_result['detected_sections'])}\n\n"
                f"--- Content Preview ---\n{scrape_result['full_text'][:2000]}..."
            )
            history.append(f"Scraped website content from {scrape_result['url']}")
        else:
            history.append(f"Failed to scrape {client_name}: {scrape_result['error']}")

    return {
        "client_context": context,
        "website_content": website_content,
        "history": history,
        "iterations": state.get("iterations", 0)
    }

@observe(name="file-processing-node")
async def file_processing_node(state: AgentState):
    """Process attached files using Google Drive API."""
    file_ids = state.get("attached_files", [])
    history = state.get("history", [])
    
    if not file_ids:
        # No files attached, skip processing
        return {
            "file_summaries": [],
            "history": history
        }
    
    file_summaries = []
    
    for file_id in file_ids:
        content = await drive_service.get_file_content(file_id)
        file_summaries.append(content)
        
        # Log the processing
        if content.get("error"):
            history.append(f"Error processing file {file_id}: {content['error']}")
        else:
            history.append(f"Processed file '{content.get('filename')}' ({content.get('type')})")
    
    return {
        "file_summaries": file_summaries,
        "history": history
    }

@observe(name="validate-request-node")
def validate_request_node(state: AgentState):
    """Classify the request and check completeness."""
    request = state["raw_request"]
    context = state.get("client_context", {})
    client_category = state.get("client_category")
    file_summaries = state.get("file_summaries", [])
    website_content = state.get("website_content")
    logs = state.get("logs", {})
    history = state.get("history", [])

    result = request_validator.validate_and_classify(
        request,
        context,
        client_category=client_category,
        file_summaries=file_summaries,
        website_content=website_content
    )
    validator.report_usage(result["usage"], result["model"])

    classification = result["content"]

    logs["request_validation"] = {
        "model": result["model"],
        "usage": result["usage"],
        "classification": classification,
    }

    needs_admin = not classification["complete"]

    history.append(
        f"Request classified as '{classification['primary_category']}' "
        f"(complete={classification['complete']}, confidence={classification['confidence']})"
    )

    return {
        "request_category": classification["primary_category"],
        "request_subcategories": classification.get("subcategories", []),
        "is_request_complete": classification["complete"],
        "missing_information": classification.get("missing", []),
        "needs_admin_review": needs_admin,
        "logs": logs,
        "history": history,
    }


@observe(name="create-admin-task-node")
async def create_admin_task_node(state: AgentState):
    """Create a clarification task in Theo's ClickUp list for incomplete requests."""
    client_id = state["client_id"]
    request = state["raw_request"]
    category = state.get("request_category", "unclear")
    missing = state.get("missing_information", [])
    context = state.get("client_context", {})
    logs = state.get("logs", {})
    history = state.get("history", [])

    # Build markdown description
    missing_md = "\n".join(f"- {item}" for item in missing) if missing else "- No specific items identified"
    description = (
        f"## Original Request\n"
        f"> {request}\n\n"
        f"## Classification\n"
        f"- **Category:** {category}\n"
        f"- **Subcategories:** {', '.join(state.get('request_subcategories', []) or ['none'])}\n\n"
        f"## Missing Information\n"
        f"The following details are needed before this can be turned into a technical spec:\n\n"
        f"{missing_md}\n\n"
        f"## Client Context\n"
        f"```\n{context}\n```\n"
    )

    title = f"[{client_id}] Clarify: {request[:50]}{'...' if len(request) > 50 else ''}"
    tags = ["needs-clarification", category, "agency-ai"]

    result = await clickup_service.create_task(
        list_id=THEO_LIST_ID,
        name=title,
        description=description,
        tags=tags,
    )

    task_id = result.get("id")
    task_url = result.get("url")

    # Upload attachments so Theo has full context
    attached_files = state.get("attached_files", [])
    if task_id and attached_files:
        for file_id in attached_files:
            meta = await drive_service.get_file_metadata(file_id)
            if not meta:
                continue

            filename = meta.get("name", "unknown_file")
            mime_type = meta.get("mimeType")

            content = await drive_service.download_file(file_id)
            if content:
                att_res = await clickup_service.create_task_attachment(
                    task_id, content, filename, mime_type
                )
                if att_res.get("date"):
                    logs.setdefault("attachments", []).append(f"Uploaded: {filename}")
                else:
                    logs.setdefault("attachments", []).append(f"Failed: {filename}")

    logs["admin_task"] = {
        "id": task_id,
        "url": task_url,
        "name": title,
    }

    history.append(f"Created admin review task in ClickUp: {task_url or task_id}")

    get_client().score_current_trace(name="workflow_interrupt", value=1, data_type="NUMERIC")

    return {
        "admin_task_id": task_url,
        "logs": logs,
        "history": history,
    }


@observe(name="architect-node")
def architect_node(state: AgentState):
    """Generate the technical plan."""
    request = state["raw_request"]
    context = state.get("client_context", {})
    client_priority = state.get("client_priority")
    request_category = state.get("request_category")
    file_summaries = state.get("file_summaries", [])
    website_content = state.get("website_content")
    logs = state.get("logs", {})

    # Check if we have critique from previous turn to add to context
    full_prompt_input = request
    if state.get("critique"):
        full_prompt_input += f"\n\nPREVIOUS REVIEW CRITIQUE (Fix this): {state['critique']}"

    # Agent now returns Dict with content, model, usage
    result = architect_agent.generate_plan(
        full_prompt_input,
        context,
        client_priority=client_priority,
        request_category=request_category,
        file_summaries=file_summaries,
        website_content=website_content
    )
    validator.report_usage(result["usage"], result["model"])

    # Update logs
    logs["architect"] = {
        "model": result["model"],
        "usage": result["usage"],
        "full_output": result["content"] 
    }
    
    return {
        "task_md": result["content"],
        "logs": logs,
        "history": state["history"] + ["Generated Technical Plan"]
    }

@observe(name="qa-reviewer-node")
def qa_reviewer_node(state: AgentState):
    """Review the plan."""
    plan_data = state.get("task_md", {})
    # If plan_data is a dict (from new structured agent), get markdown. Else use as is (legacy).
    if isinstance(plan_data, dict):
        plan_content = plan_data.get("description_markdown", "")
    else:
        plan_content = str(plan_data)
        
    request = state["raw_request"]
    logs = state.get("logs", {})
    
    # Run lightweight validation checks
    validator.validate(request_text=request, plan=plan_content)

    # Agent now returns Dict
    result = review_agent.review_plan(request, plan_content)
    validator.report_usage(result["usage"], result["model"])
    review_content = result["content"]
    
    # Update logs
    iteration = state.get("iterations", 0)
    logs[f"qa_review_{iteration}"] = {
        "model": result["model"],
        "usage": result["usage"],
        "result": review_content  # "APPROVE" or critique
    }
    
    critique = None
    if "APPROVE" not in review_content:
        critique = review_content
        
    return {
        "critique": critique,
        "iterations": state["iterations"] + 1,
        "logs": logs,
        "history": state["history"] + [f"QA Review: {'APPROVED' if not critique else 'REJECTED: ' + critique}"]
    }

@observe(name="clickup-push-node")
async def clickup_push_node(state: AgentState):
    """Push to ClickUp."""
    # Push to specific list: Dinesh - Upwork
    list_id = DINESH_UPWORK_LIST_ID
    logs = state.get("logs", {})
    
    plan_data = state.get("task_md", {})
    is_struct = isinstance(plan_data, dict)
    
    if is_struct:
        title = plan_data.get("task_name", f"Feature: {state['client_id']}")
        description = plan_data.get("description_markdown", "")
        tags = plan_data.get("tags", [])
        checklist_items = plan_data.get("checklist", [])
        priority_str = plan_data.get("priority")
        priority_reasoning = plan_data.get("priority_reasoning")
    else:
        # Fallback for string
        lines = str(plan_data).split("\n")
        title = lines[0].strip("# ").strip() if lines else f"Feature: {state['client_id']}"
        description = str(plan_data)
        tags = ["agency-ai", "automated"]
        checklist_items = []
        priority_str = None
        priority_reasoning = None

    # Map priority to ClickUp API format
    priority = map_priority_to_clickup(priority_str) if priority_str else None

    # Add priority context to description if reasoning exists
    if priority_reasoning:
        description = f"{description}\n\n---\n\n**Priority Decision**: {priority_str}\n*{priority_reasoning}*"

    # Prefix title with Client ID for clarity if not present
    client_prefix = f"[{state['client_id']}] "
    if not title.startswith("["):
        title = client_prefix + title

    # Ensure agency-ai tag is present
    if "agency-ai" not in tags:
        tags.append("agency-ai")

    # 1. Create Task
    result = await clickup_service.create_task(
        list_id=list_id,
        name=title,
        description=description,
        tags=tags,
        priority=priority
    )
    
    task_id = result.get("id")
    task_url = result.get("url")

    # 2. Add Checklist if task created and items exist
    if task_id and checklist_items:
        checklist_res = await clickup_service.create_checklist(task_id, "Definition of Done")
        checklist_id = checklist_res.get("checklist", {}).get("id")
        
        if checklist_id:
            for item in checklist_items:
                await clickup_service.create_checklist_item(checklist_id, item)

    # 3. Upload Attachments
    attached_files = state.get("attached_files", [])
    if task_id and attached_files:
        for file_id in attached_files:
            # Get file metadata for name/type
            meta = await drive_service.get_file_metadata(file_id)
            if not meta:
                continue
                
            filename = meta.get("name", "unknown_file")
            mime_type = meta.get("mimeType")
            
            # Download content
            content = await drive_service.download_file(file_id)
            if content:
                print(f"Uploading attachment {filename} to ClickUp task {task_id}...")
                att_res = await clickup_service.create_task_attachment(
                    task_id, 
                    content, 
                    filename, 
                    mime_type
                )
                if att_res.get("date"): # Successful upload usually returns date
                    logs.setdefault("attachments", []).append(f"Uploaded: {filename}")
                else:
                    logs.setdefault("attachments", []).append(f"Failed: {filename}")

    # Log task details
    logs["clickup_task"] = {
        "url": task_url,
        "id": task_id,
        "name": title,
        "payload_sent": {
            "name": title,
            "description": description,
            "tags": tags,
            "checklist": checklist_items,
            "priority": priority,
            "priority_string": priority_str,
            "priority_reasoning": priority_reasoning
        },
        "debug_is_structured": is_struct
    }

    get_client().score_current_trace(name="workflow_success", value=1, data_type="NUMERIC")

    return {
        "logs": logs,
        "history": state["history"] + [f"Pushed to ClickUp: {result.get('url', 'success')}"]
    }

def emit_to_n8n(state):
    """
    Sends the final state (or specific results) to n8n.
    """
    n8n_url = "https://primary-production-3d4e5.up.railway.app/webhook/33b65cfd-705e-4137-9aec-8a2f1fc23e44"
    
    logs = state.get("logs", {})
    clickup_task_url = (
        logs.get("clickup_task", {}).get("url")
        or logs.get("admin_task", {}).get("url")
    )

    payload = {
        "event": "workflow_completed",
        "client_id": state.get("client_id", "unknown"),
        "clickup_task_url": clickup_task_url,
        "needs_admin_review": state.get("needs_admin_review", False),
        "request_category": state.get("request_category"),
    }
    
    try:
        # Use a timeout so LangGraph doesn't get stuck if n8n is slow
        response = requests.post(n8n_url, json=payload, timeout=10)
        response.raise_for_status()
        print("Successfully notified n8n")
    except Exception as e:
        print(f"Failed to notify n8n: {e}")
    
    # Returning the state unchanged, as this is just a side-effect node
    return state

# --- Routing Logic ---

def route_after_validation(state: AgentState) -> Literal["architect", "create_admin_task"]:
    if state.get("needs_admin_review"):
        return "create_admin_task"
    return "architect"


def should_continue(state: AgentState) -> Literal["architect", "push_to_clickup", "create_admin_task"]:
    if state.get("critique") and state["iterations"] < 3:
        return "architect"
    if state.get("critique"):
        # 3 rejections — route to admin review
        return "create_admin_task"
    return "push_to_clickup"

# --- Graph Construction ---

workflow = StateGraph(AgentState)

workflow.add_node("enrichment", enrichment_node)
workflow.add_node("file_processing", file_processing_node)
workflow.add_node("validate_request", validate_request_node)
workflow.add_node("create_admin_task", create_admin_task_node)
workflow.add_node("architect", architect_node)
workflow.add_node("qa_reviewer", qa_reviewer_node)
workflow.add_node("push_to_clickup", clickup_push_node)
workflow.add_node("emit_to_n8n", emit_to_n8n)

workflow.set_entry_point("enrichment")
workflow.add_edge("enrichment", "file_processing")
workflow.add_edge("file_processing", "validate_request")

workflow.add_conditional_edges(
    "validate_request",
    route_after_validation,
    {
        "architect": "architect",
        "create_admin_task": "create_admin_task",
    }
)

workflow.add_edge("architect", "qa_reviewer")

workflow.add_conditional_edges(
    "qa_reviewer",
    should_continue,
    {
        "architect": "architect",
        "push_to_clickup": "push_to_clickup",
        "create_admin_task": "create_admin_task",
    }
)

workflow.add_edge("create_admin_task", "emit_to_n8n")
workflow.add_edge("push_to_clickup", "emit_to_n8n")
workflow.add_edge("emit_to_n8n", END)

app_graph = workflow.compile()
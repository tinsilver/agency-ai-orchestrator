from typing import Literal
from langgraph.graph import StateGraph, END

from app.state import AgentState
from app.services.clickup import ClickUpService
from app.agents.architect import ArchitectAgent
from app.agents.review import ReviewAgent

# Initialize Services & Agents
# airtable_service removed
clickup_service = ClickUpService()
architect_agent = ArchitectAgent()
review_agent = ReviewAgent()

# --- Node Definitions ---

# List IDs from discovery
SITE_PARAMETERS_LIST_ID = "901520311911"
DINESH_UPWORK_LIST_ID = "901520311855"

async def enrichment_node(state: AgentState):
    """Fetch client data from ClickUp Task."""
    client_name = state["client_id"] # Matches "Client ID" from form, e.g. domain name
    
    # 1. Find the task in "Site Parameters" list that matches the client name
    tasks = await clickup_service.get_tasks(SITE_PARAMETERS_LIST_ID)
    target_task = next((t for t in tasks if t["name"] == client_name), None)
    
    context = {}
    history = state.get("history", [])

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
        # Fallback for demo if not found?
        context["Note"] = "Context not found, using defaults if any"

    history.append(action)
    
    return {
        "client_context": context,
        "history": history,
        "iterations": state.get("iterations", 0)
    }

def architect_node(state: AgentState):
    """Generate the technical plan."""
    request = state["raw_request"]
    context = state.get("client_context", {})
    logs = state.get("logs", {})
    
    # Check if we have critique from previous turn to add to context
    full_prompt_input = request
    if state.get("critique"):
        full_prompt_input += f"\n\nPREVIOUS REVIEW CRITIQUE (Fix this): {state['critique']}"

    # Agent now returns Dict with content, model, usage
    result = architect_agent.generate_plan(full_prompt_input, context)
    
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
    
    # Agent now returns Dict
    result = review_agent.review_plan(request, plan_content)
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
    else:
        # Fallback for string
        lines = str(plan_data).split("\n")
        title = lines[0].strip("# ").strip() if lines else f"Feature: {state['client_id']}"
        description = str(plan_data)
        tags = ["agency-ai", "automated"]
        checklist_items = []

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
        tags=tags
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

    # Log task details
    logs["clickup_task"] = {
        "url": task_url,
        "id": task_id,
        "name": title,
        "payload_sent": {
            "name": title,
            "description": description,
            "tags": tags,
            "checklist": checklist_items
        },
        "debug_is_structured": is_struct
    }
    
    return {
        "logs": logs,
        "history": state["history"] + [f"Pushed to ClickUp: {result.get('url', 'success')}"]
    }

# --- Routing Logic ---

def should_continue(state: AgentState) -> Literal["architect", "push_to_clickup"]:
    # Loop back if there is valid critique and < 3 iterations
    if state.get("critique") and state["iterations"] < 3:
        return "architect"
    return "push_to_clickup"

# --- Graph Construction ---

workflow = StateGraph(AgentState)

workflow.add_node("enrichment", enrichment_node)
workflow.add_node("architect", architect_node)
workflow.add_node("qa_reviewer", qa_reviewer_node)
workflow.add_node("push_to_clickup", clickup_push_node)

workflow.set_entry_point("enrichment")
workflow.add_edge("enrichment", "architect")
workflow.add_edge("architect", "qa_reviewer")

workflow.add_conditional_edges(
    "qa_reviewer",
    should_continue,
    {
        "architect": "architect",
        "push_to_clickup": "push_to_clickup"
    }
)

workflow.add_edge("push_to_clickup", END)

app_graph = workflow.compile()
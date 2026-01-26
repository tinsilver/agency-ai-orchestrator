from typing import TypedDict, List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AgentState(TypedDict):
    """
    Tracks the workflow state for the Agency AI Orchestrator.
    """
    client_id: str
    raw_request: str
    client_context: Optional[Dict[str, Any]]  # Data from Airtable (tech stack, brand)
    task_md: Optional[str]                    # Generated Markdown specs
    mermaid_code: Optional[str]               # Generated Mermaid diagrams
    critique: Optional[str]                   # Feedback from QA Agent
    iterations: int                           # QA loop counter
    history: List[str]                        # Audit log of actions
    logs: Dict[str, Any]                      # Structured logs (tokens, models, timing)

class WebhookPayload(BaseModel):
    """
    Input schema for the FastAPI webhook.
    """
    client_id: str = Field(..., description="Unique ID of the client in Airtable")
    request_text: str = Field(..., description="Natural language change request")

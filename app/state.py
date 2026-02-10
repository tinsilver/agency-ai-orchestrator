from typing import TypedDict, List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class AgentState(TypedDict):
    """
    Tracks the workflow state for the Agency AI Orchestrator.
    """
    client_id: str
    raw_request: str
    client_context: Optional[Dict[str, Any]]  # Data from ClickUp (tech stack, brand)
    attached_files: Optional[List[str]]       # List of Google Drive file IDs
    file_summaries: Optional[List[Dict[str, Any]]]  # Extracted file content and metadata
    website_content: Optional[str]            # Scraped website structure/content
    task_md: Optional[Union[str, Dict[str, Any]]]  # Generated plan (dict from architect or legacy string)
    mermaid_code: Optional[str]               # Generated Mermaid diagrams
    critique: Optional[str]                   # Feedback from QA Agent
    iterations: int                           # QA loop counter
    history: List[str]                        # Audit log of actions
    logs: Dict[str, Any]                      # Structured logs (tokens, models, timing)
    input_eval_passed: Optional[bool]         # Whether Eval 1 (input validation) passed
    input_eval_result: Optional[Dict[str, Any]]  # Full Eval 1 result details

class WebhookPayload(BaseModel):
    """
    Input schema for the FastAPI webhook.
    """
    client_id: str = Field(..., description="Unique ID of the client (domain name)")
    request_text: str = Field(..., description="Natural language change request")
    file_ids: Optional[List[str]] = Field(default=None, description="Google Drive file IDs for attachments")

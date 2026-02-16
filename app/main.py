from dotenv import load_dotenv

# Load environment variables first (for local dev; Railway provides them automatically)
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager
from app.graph import app_graph
from app.state import WebhookPayload
from app.utils import sanitize_domain
from langfuse import observe, get_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Flush pending Langfuse events on shutdown
    get_client().flush()

app = FastAPI(title="Agency AI Orchestrator", lifespan=lifespan, redirect_slashes=False)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Agency AI Orchestrator"}

@app.post("/webhook")
@observe(name="webhook-workflow")
async def handle_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """
    Receives a webhook trigger (e.g. from a form or external app).
    Runs the LangGraph workflow.
    """
    # Sanitize client_id to ensure consistent domain format
    # Handles: "https://google.co.uk" → "google.co.uk", "www.example.com/" → "example.com"
    clean_client_id = sanitize_domain(payload.client_id)

    langfuse = get_client()
    langfuse.update_current_trace(
        session_id=f"webhook-{clean_client_id}",
        user_id=clean_client_id,
        tags=["webhook", "production"],
    )

    input_state = {
        "client_id": clean_client_id,
        "raw_request": payload.request_text,
        "client_priority": payload.client_priority,
        "client_category": payload.client_category,
        "attached_files": payload.attached_files,
        "history": [],
        "iterations": 0
    }

    try:
        result = await app_graph.ainvoke(input_state)
        return {
            "status": "success",
            "history": result.get("history")
        }
    except Exception as e:
        print(f"Workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

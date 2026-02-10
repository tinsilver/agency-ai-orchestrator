from fastapi import FastAPI, HTTPException, BackgroundTasks
from app.graph import app_graph
from app.state import WebhookPayload

app = FastAPI(title="Agency AI Orchestrator")

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Agency AI Orchestrator"}

@app.post("/webhook")
async def handle_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """
    Receives a webhook trigger (e.g. from a form or external app).
    Runs the LangGraph workflow.
    """
    input_state = {
        "client_id": payload.client_id,
        "raw_request": payload.request_text,
        "attached_files": payload.file_ids or [],
        "history": [],
        "iterations": 0
    }
    
    # For sync handling (simpler for now to return result, 
    # but in prod background_tasks better for long running agents)
    try:
        # invoke() is synchronous, but we can wrap it if needed. 
        # Since we use async clickup, we might want to use ainvoke if LangGraph supports it effectively for this structure.
        # But app_graph.invoke is standard.
        result = await app_graph.ainvoke(input_state)

        # Check if request was rejected by input eval
        if not result.get("input_eval_passed", True):
            eval_data = result.get("input_eval_result", {})
            return {
                "status": "rejected",
                "reason": eval_data.get("reason", "Request did not pass input validation."),
                "category": eval_data.get("category", "unknown"),
                "score": eval_data.get("score", 0.0),
                "auto_fail_triggered": eval_data.get("auto_fail_triggered", False),
                "failed_criteria": eval_data.get("failed_criteria_fixes", []),
                "bar_raiser_decision": eval_data.get("bar_raiser_decision", ""),
                "suggested_clarification": eval_data.get("suggested_clarification", ""),
                "history": result.get("history"),
            }

        return {
            "status": "success",
            "history": result.get("history")
        }
    except Exception as e:
        # Log error
        print(f"Workflow failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

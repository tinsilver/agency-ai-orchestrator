import asyncio
import os
from unittest.mock import MagicMock, patch
from app.state import AgentState

# Set dummy key BEFORE importing anything that initializes ChatAnthropic
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-dummy"

async def run_verification():
    print("Starting Verification (with mocks)...")
    
    # Mocking external dependencies
    with patch("app.graph.clickup_service") as mock_clickup, \
         patch("app.graph.architect_agent") as mock_architect, \
         patch("app.graph.review_agent") as mock_review:
         
        # Async mock for ClickUp - used for BOTH enrichment and creation
        mock_clickup.get_task_details = MagicMock()
        mock_clickup.create_task = MagicMock()

        async def async_get_task(*args, **kwargs):
             return {
                "name": "Test Client",
                "custom_fields": [
                     {"name": "Tech Stack", "value": "Python, React"},
                     {"name": "Brand Guidelines", "value": "Dark Mode"}
                 ]
             }
        
        async def async_create_task(*args, **kwargs):
            return {"url": "http://clickup.com/task/123"}
            
        mock_clickup.get_task_details.side_effect = async_get_task
        mock_clickup.create_task.side_effect = async_create_task
        
        mock_architect.generate_plan.return_value = """# Feature Plan
## Tech Specs
- Create endpoint
```mermaid
graph TD;
    A-->B;
```
"""
        mock_review.review_plan.return_value = "APPROVE"
        
        # Async mock for ClickUp
        mock_clickup.create_task = MagicMock()
        async def async_create_task(*args, **kwargs):
            return {"url": "http://clickup.com/task/123"}
        mock_clickup.create_task.side_effect = async_create_task

        # Import graph AFTER patching if possible, but since it's already imported in app.graph,
        # we strictly patched the instances in app.graph module using 'app.graph.airtable_service' etc.
        from app.graph import app_graph

        input_state = {
            "client_id": "recMock123",
            "raw_request": "Build a thing",
            "history": [],
            "iterations": 0
        }
        
        try:
            print(f"Invoking graph with input: {input_state}")
            result = await app_graph.ainvoke(input_state)
            
            print("\n--- Workflow Result ---")
            print(f"History: {result.get('history')}")
            
            # Validation
            history = result.get("history", [])
            
            # Check for key milestones
            has_enrichment = any("Enriched context from ClickUp" in h for h in history)
            has_plan = any("Generated Technical Plan" in h for h in history)
            has_approval = any("QA Review: APPROVED" in h for h in history)
            has_push = any("Pushed to ClickUp" in h for h in history)
            
            if has_enrichment and has_plan and has_approval and has_push:
                print("\n✅ SUCCESS: Graph executed all nodes correctly with mocks.")
            else:
                print("\n❌ FAILURE: Missing steps.")
                print(f"Enriched: {has_enrichment}")
                print(f"Planned: {has_plan}")
                print(f"Approved: {has_approval}")
                print(f"Pushed: {has_push}")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_verification())
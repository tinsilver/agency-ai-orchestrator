import asyncio
import json
import os
import sys

# Ensure app can be imported
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

import app._compat  # noqa: F401 - Patch pydantic v1 for Python 3.14 before langfuse import

from app.graph import app_graph
from langfuse import observe, get_client, propagate_attributes

import time
import uuid

@observe(name="demo-workflow")
async def run_demo():
    """Run demo workflow with optional file attachments."""
    import sys

    # Determine which scenario to run
    scenario = sys.argv[1] if len(sys.argv) > 1 else "no_files"

    request_id = str(uuid.uuid4())
    start_time = time.time()

    langfuse = get_client()
    langfuse.update_current_trace(
        session_id=f"demo-{request_id}",
        user_id="demo-user",
        tags=["demo", scenario],
    )
    
    if scenario == "with_files":
        # Scenario with file attachments
        input_json_str = """
{
  "Client ID": "thebusinessbeanstalk.co.uk",
  "Client Request": "See attached wireframe for new contact form",
  "Category": "Website Development",
  "Priority": "High",
  "Attached Files": ["mock_file_id_1", "mock_file_id_2"]
}
"""
    elif scenario == "seo_content":
        # Scenario for SEO/Content generation
        input_json_str = """
{
  "Client ID": "thebusinessbeanstalk.co.uk",
  "Client Request": "Create a new 'Careers' page for our agency. We need copy for a Senior Developer role.",
  "Category": "Content Creation",
  "Priority": "Medium",
  "Timestamp": "2026-02-01T15:00:00Z"
}
"""
    else:
        # Scenario without files (default)
        input_json_str = """
{
  "Client ID": "thebusinessbeanstalk.co.uk",
  "Client Request": "I'd like to add a button to the home page, just below the hero, that links to the Services page.",
  "Category": "Website Design",
  "Priority": "Medium",
  "Timestamp": "2026-01-25T18:00:00Z"
}
"""
    
    input_data = json.loads(input_json_str)
    
    print(f"--- 🚀 Starting Agency AI Workflow Demo (Scenario: {scenario}, Req: {request_id}) ---")
    print(f"Input: {json.dumps(input_data, indent=2)}")
    
    # 2. Map to AgentState
    initial_state = {
        "client_id": input_data["Client ID"], 
        "raw_request": input_data["Client Request"],
        "attached_files": input_data.get("Attached Files", []),
        "history": [],
        "iterations": 0,
        "logs": {} # Initialize logs
    }
    
    # 3. Run Graph
    print("\n--- ⏳ Running Workflow... ---")
    try:
        result = await app_graph.ainvoke(initial_state)
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n--- ✅ Workflow Complete ---")
        
        # 4. Show Results & Logging
        history = result.get("history", [])
        logs = result.get("logs", {})
        
        print("\n📜 Execution History:")
        for event in history:
            print(f"  - {event}")
            
        print("\n📝 Generated Plan (Snippet):")
        plan = result.get("task_md", "No plan generated")
        print(plan[:300] + "..." if len(plan) > 300 else plan)
        
        # Prepare Log Output
        log_entry = {
            "request_id": request_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_time)),
            "duration_seconds": round(duration, 2),
            "input": input_data,
            "agent_execution": logs,
            "final_status": "SUCCESS",
            "task_url": logs.get("clickup_task", {}).get("url"),
            "task_name": logs.get("clickup_task", {}).get("name")
        }
        
        # Save to file
        log_filename = f"workflow_log_{request_id}.json"
        with open(log_filename, "w") as f:
            json.dump(log_entry, f, indent=2)
        print(f"\n📁 Log saved to: {log_filename}")

        # Cleanup Instructions
        task_id = logs.get("clickup_task", {}).get("id")
        task_url = logs.get("clickup_task", {}).get("url")
        
        print("\n\n--- 🧹 Cleanup Command ---")
        if task_id:
            print(f"Task Created: {task_url}")
            print(f"To delete this task, run:")
            print(f"curl -X DELETE https://api.clickup.com/api/v2/task/{task_id} -H 'Authorization: {os.environ.get('CLICKUP_API_KEY')}'")
        else:
            print("Could not find Task ID for cleanup.")
            
    except Exception as e:
        print(f"\n❌ Workflow Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_demo())
    # Flush all pending Langfuse events before exit
    get_client().flush()

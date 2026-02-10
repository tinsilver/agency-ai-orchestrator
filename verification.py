import asyncio
import os
from unittest.mock import MagicMock, patch
from app.state import AgentState

# Set dummy key BEFORE importing anything that initializes ChatAnthropic
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-dummy"


async def _setup_common_mocks(mock_clickup):
    """Configure shared ClickUp mocks for both scenarios."""
    mock_clickup.get_task_details = MagicMock()
    mock_clickup.get_tasks = MagicMock()
    mock_clickup.create_task = MagicMock()

    async def async_get_tasks(*args, **kwargs):
        return []

    async def async_get_task_details(*args, **kwargs):
        return {
            "name": "Test Client",
            "custom_fields": [
                {"name": "Tech Stack", "value": "Python, React"},
                {"name": "Brand Guidelines", "value": "Dark Mode"}
            ]
        }

    async def async_create_task(*args, **kwargs):
        return {"id": "mock-task-123", "url": "http://clickup.com/task/123"}

    mock_clickup.get_tasks.side_effect = async_get_tasks
    mock_clickup.get_task_details.side_effect = async_get_task_details
    mock_clickup.create_task.side_effect = async_create_task


async def run_complete_request_scenario():
    """Scenario 1: Complete request flows through architect -> qa -> clickup push."""
    print(f"\n{'=' * 60}")
    print("SCENARIO 1: Complete request (full flow)")
    print('=' * 60)

    with patch("app.graph.clickup_service") as mock_clickup, \
         patch("app.graph.architect_agent") as mock_architect, \
         patch("app.graph.review_agent") as mock_review, \
         patch("app.graph.request_validator") as mock_validator:

        await _setup_common_mocks(mock_clickup)

        # Validator says: complete request
        mock_validator.validate_and_classify.return_value = {
            "content": {
                "primary_category": "feature_request",
                "subcategories": [],
                "complete": True,
                "missing": [],
                "confidence": 0.95,
                "reasoning": "Complete feature request with clear requirements",
            },
            "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        mock_architect.generate_plan.return_value = {
            "content": {
                "task_name": "Build a contact form",
                "description_markdown": "## Task Summary\nBuild contact form\n## Execution Steps\n1. Create form",
                "checklist": ["Build form", "Add validation"],
                "tags": ["feature", "agency-ai"],
            },
            "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 200, "output_tokens": 300},
        }

        mock_review.review_plan.return_value = {
            "content": "APPROVE",
            "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 150, "output_tokens": 10},
        }

        # Need to mock create_checklist for the push node
        mock_clickup.create_checklist = MagicMock()
        mock_clickup.create_checklist_item = MagicMock()
        async def async_create_checklist(*args, **kwargs):
            return {"checklist": {"id": "mock-checklist-id"}}
        async def async_create_checklist_item(*args, **kwargs):
            return {}
        mock_clickup.create_checklist.side_effect = async_create_checklist
        mock_clickup.create_checklist_item.side_effect = async_create_checklist_item

        from app.graph import app_graph

        input_state = {
            "client_id": "recMock123",
            "raw_request": "Build a contact form with name, email, phone and message fields",
            "history": [],
            "iterations": 0,
        }

        try:
            result = await app_graph.ainvoke(input_state)
            history = result.get("history", [])

            print(f"History: {history}")

            has_classification = any("Request classified" in h for h in history)
            has_plan = any("Generated Technical Plan" in h for h in history)
            has_approval = any("QA Review: APPROVED" in h for h in history)
            has_push = any("Pushed to ClickUp" in h for h in history)
            no_admin = result.get("admin_task_id") is None

            if has_classification and has_plan and has_approval and has_push and no_admin:
                print("\n✅ SCENARIO 1 PASSED: Complete request flowed through full pipeline.")
            else:
                print("\n❌ SCENARIO 1 FAILED: Missing steps.")
                print(f"  Classified: {has_classification}")
                print(f"  Planned: {has_plan}")
                print(f"  Approved: {has_approval}")
                print(f"  Pushed: {has_push}")
                print(f"  No admin task: {no_admin}")

        except Exception as e:
            print(f"\n❌ SCENARIO 1 ERROR: {e}")
            import traceback
            traceback.print_exc()


async def run_incomplete_request_scenario():
    """Scenario 2: Incomplete request routes to admin task, skips architect."""
    print(f"\n{'=' * 60}")
    print("SCENARIO 2: Incomplete request (admin task route)")
    print('=' * 60)

    with patch("app.graph.clickup_service") as mock_clickup, \
         patch("app.graph.architect_agent") as mock_architect, \
         patch("app.graph.review_agent") as mock_review, \
         patch("app.graph.request_validator") as mock_validator:

        await _setup_common_mocks(mock_clickup)

        # Validator says: incomplete request
        mock_validator.validate_and_classify.return_value = {
            "content": {
                "primary_category": "bug_fix",
                "subcategories": [],
                "complete": False,
                "missing": [
                    "Which page is the contact form on?",
                    "What error message do you see?",
                    "What should happen when the form is submitted?",
                ],
                "confidence": 0.7,
                "reasoning": "Bug report but missing page, error details, and expected behavior",
            },
            "model": "claude-haiku-4-5-20251001",
            "usage": {"input_tokens": 80, "output_tokens": 60},
        }

        from app.graph import app_graph

        input_state = {
            "client_id": "recMock456",
            "raw_request": "The contact form isn't working",
            "history": [],
            "iterations": 0,
        }

        try:
            result = await app_graph.ainvoke(input_state)
            history = result.get("history", [])

            print(f"History: {history}")

            has_classification = any("Request classified" in h for h in history)
            has_admin_task = any("Created admin review task" in h for h in history)
            no_plan = not any("Generated Technical Plan" in h for h in history)
            no_approval = not any("QA Review" in h for h in history)
            has_admin_id = result.get("admin_task_id") is not None

            # Verify architect was NOT called
            architect_called = mock_architect.generate_plan.called

            if has_classification and has_admin_task and no_plan and no_approval and not architect_called and has_admin_id:
                print("\n✅ SCENARIO 2 PASSED: Incomplete request routed to admin task, architect skipped.")
            else:
                print("\n❌ SCENARIO 2 FAILED:")
                print(f"  Classified: {has_classification}")
                print(f"  Admin task created: {has_admin_task}")
                print(f"  Plan skipped: {no_plan}")
                print(f"  QA skipped: {no_approval}")
                print(f"  Architect not called: {not architect_called}")
                print(f"  Admin task ID set: {has_admin_id}")

        except Exception as e:
            print(f"\n❌ SCENARIO 2 ERROR: {e}")
            import traceback
            traceback.print_exc()


async def run_verification():
    print("Starting Verification (with mocks)...")
    await run_complete_request_scenario()
    await run_incomplete_request_scenario()
    print("\n--- Verification complete ---")


if __name__ == "__main__":
    asyncio.run(run_verification())

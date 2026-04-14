"""
End-to-end test for enrichment workflow.
Tests Example 4: Add social media field to contact form (theoruby.com)
"""
import asyncio
import json
from app.graph import app_graph
from app.state import AgentState
from langfuse import get_client


async def test_enrichment_workflow():
    """Test the enrichment workflow with a real example."""

    print("=" * 80)
    print("ENRICHMENT WORKFLOW - END-TO-END TEST")
    print("=" * 80)
    print()

    # Example 4 from Example client requests.md
    test_request = {
        "client_id": "www.theoruby.com",
        "raw_request": "I would like you to add a new field to my contact form to ask people for their social media accounts",
        "form_source": "test",
        "priority": 2,
        "category": None,
        "attached_files": []
    }

    print("📝 Test Request:")
    print(f"   Client: {test_request['client_id']}")
    print(f"   Request: {test_request['raw_request']}")
    print()

    # Create initial state
    input_state: AgentState = {
        "client_id": test_request["client_id"],
        "raw_request": test_request["raw_request"],
        "form_source": test_request["form_source"],
        "priority": test_request["priority"],
        "category": test_request.get("category"),
        "attached_files": test_request.get("attached_files", []),

        # Enrichment initialization
        "enrichment_iteration": 0,
        "enrichment_history": [],
        "dynamic_context": {},
        "tool_usage_stats": {},
        "total_enrichment_tokens": 0,
        "max_enrichment_tokens": 500_000,
        "enrichment_complete": False,
        "enrichment_stop_reason": None,
    }

    print("🚀 Starting workflow execution...")
    print()

    try:
        # Execute workflow
        final_state = await app_graph.ainvoke(input_state)

        print("=" * 80)
        print("✅ WORKFLOW COMPLETED")
        print("=" * 80)
        print()

        # Display enrichment results
        print("📊 ENRICHMENT RESULTS:")
        print("-" * 80)
        print(f"Iterations:        {final_state.get('enrichment_iteration', 0)}")
        print(f"Complete:          {final_state.get('enrichment_complete', False)}")
        print(f"Stop Reason:       {final_state.get('enrichment_stop_reason', 'N/A')}")
        print(f"Total Tokens:      {final_state.get('total_enrichment_tokens', 0):,}")
        print(f"Request Complete:  {final_state.get('is_request_complete', False)}")
        print()

        # Display tool usage
        tool_usage = final_state.get('tool_usage_stats', {})
        if tool_usage:
            print("🔧 TOOL USAGE:")
            print("-" * 80)
            for tool_name, stats in tool_usage.items():
                if isinstance(stats, dict):
                    calls = stats.get('calls', 0)
                    max_calls = stats.get('max_calls', 0)
                    print(f"   {tool_name:25} {calls}/{max_calls} calls")
            print()

        # Display enrichment history
        enrichment_history = final_state.get('enrichment_history', [])
        if enrichment_history:
            print("📜 ENRICHMENT HISTORY:")
            print("-" * 80)
            for iteration_data in enrichment_history:
                iteration = iteration_data.get('iteration', 0)
                tools_used = iteration_data.get('tools_used', [])
                questions_answered = iteration_data.get('questions_resolved', 0)
                tokens = iteration_data.get('tokens_used', 0)
                print(f"   Iteration {iteration}:")
                print(f"      Tools:     {', '.join(tools_used) if tools_used else 'None'}")
                print(f"      Answered:  {questions_answered} questions")
                print(f"      Tokens:    {tokens:,}")
            print()

        # Display dynamic context gathered
        dynamic_context = final_state.get('dynamic_context', {})
        if dynamic_context:
            print("🔍 DYNAMIC CONTEXT GATHERED:")
            print("-" * 80)
            for key, value in dynamic_context.items():
                if isinstance(value, dict):
                    answer = value.get('answer', value)
                    source = value.get('source', 'unknown')
                    confidence = value.get('confidence', 0)
                    print(f"   {key}:")
                    print(f"      Answer:     {answer}")
                    print(f"      Source:     {source}")
                    print(f"      Confidence: {confidence:.2f}")
                else:
                    print(f"   {key}: {value}")
            print()

        # Display validation result
        print("✓ VALIDATION RESULT:")
        print("-" * 80)
        is_complete = final_state.get('is_request_complete', False)
        missing_info = final_state.get('missing_information', [])

        if is_complete:
            print("   ✅ Request is COMPLETE")
            print("   → Routed to ARCHITECT for technical planning")
        else:
            print("   ❌ Request is INCOMPLETE")
            print(f"   → Routed to ADMIN TASK (after {final_state.get('enrichment_iteration', 0)} enrichment attempts)")

            if missing_info:
                print()
                print("   Still Missing Information:")
                for i, question in enumerate(missing_info, 1):
                    print(f"      {i}. {question}")
        print()

        # Display final task
        task_created = final_state.get('task_created', False)
        if task_created:
            task_type = "Technical Spec" if is_complete else "Admin Review"
            print(f"📋 TASK CREATED: {task_type}")
            print("-" * 80)
            task_data = final_state.get('clickup_task', {})
            if task_data:
                print(f"   Task ID:   {task_data.get('id', 'N/A')}")
                print(f"   Task URL:  {task_data.get('url', 'N/A')}")
        print()

        # Langfuse trace info
        print("🔍 LANGFUSE TRACE:")
        print("-" * 80)
        print("   View detailed trace in Langfuse dashboard:")
        print("   https://langfuse-web-production-6d35.up.railway.app/traces")
        print()

        # Summary statistics
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)

        # Calculate enrichment effectiveness
        if enrichment_history:
            total_questions_answered = sum(
                h.get('questions_resolved', 0) for h in enrichment_history
            )
            initial_missing = len(final_state.get('missing_information', [])) + total_questions_answered
            answer_rate = (total_questions_answered / initial_missing * 100) if initial_missing > 0 else 0

            print(f"Initial Missing Questions:    {initial_missing}")
            print(f"Questions Answered by Tools:  {total_questions_answered}")
            print(f"Answer Rate:                  {answer_rate:.1f}%")
            print(f"Enrichment Success:           {'YES' if is_complete else 'NO'}")
        else:
            print("No enrichment was performed (request complete on first validation)")

        print()
        print("=" * 80)

        # Flush Langfuse
        get_client().flush()

        return final_state

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ ERROR")
        print("=" * 80)
        print(f"Error: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print()
    print("Starting end-to-end enrichment workflow test...")
    print()

    # Run the test
    final_state = asyncio.run(test_enrichment_workflow())

    print()
    print("✅ Test completed successfully!")
    print()

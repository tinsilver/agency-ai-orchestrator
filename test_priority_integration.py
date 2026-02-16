#!/usr/bin/env python3
"""Test priority and category integration"""

import asyncio
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from app.agents.architect import ArchitectAgent
from app.agents.request_validator import RequestValidatorAgent

def test_architect_priority():
    """Test that architect returns priority fields"""
    architect = ArchitectAgent()

    # Simulate a bug fix request with Normal client priority
    request = "The contact form is not working. When users click Submit, nothing happens."
    client_context = {"Client Name": "Test Client", "Tech Stack": "WordPress, PHP"}
    client_priority = "Normal"
    request_category = "bug_fix"

    print("=" * 60)
    print("Testing Architect Agent Priority Decision")
    print("=" * 60)
    print(f"Request: {request}")
    print(f"Client Priority: {client_priority}")
    print(f"Request Category: {request_category}")
    print()

    result = architect.generate_plan(
        request=request,
        client_context=client_context,
        client_priority=client_priority,
        request_category=request_category
    )

    plan = result["content"]
    print("ARCHITECT OUTPUT:")
    print(f"Task Name: {plan['task_name']}")
    print(f"Priority: {plan.get('priority', 'NOT SET')}")
    print(f"Priority Reasoning: {plan.get('priority_reasoning', 'NOT SET')}")
    print(f"Tags: {plan['tags']}")
    print()
    print("Description Preview:")
    print(plan['description_markdown'][:200] + "...")
    print()
    print("=" * 60)

    # Verify priority fields exist
    assert 'priority' in plan, "Priority field missing from TaskPlan!"
    assert 'priority_reasoning' in plan, "Priority reasoning missing from TaskPlan!"
    assert plan['priority'] in ['Low', 'Normal', 'High', 'Urgent'], f"Invalid priority: {plan['priority']}"

    print(f"✅ Priority set to: {plan['priority']}")
    print(f"✅ Reasoning: {plan['priority_reasoning']}")


def test_validator_category():
    """Test that validator considers client category"""
    validator = RequestValidatorAgent()

    # Client suggests content_update but it's clearly a bug
    request = "The search function is returning 500 errors"
    client_context = {"Client Name": "Test Client"}
    client_category = "content_update"

    print()
    print("=" * 60)
    print("Testing Validator Category Override")
    print("=" * 60)
    print(f"Request: {request}")
    print(f"Client Category Suggestion: {client_category}")
    print()

    result = validator.validate_and_classify(
        request=request,
        client_context=client_context,
        client_category=client_category
    )

    classification = result["content"]
    print("VALIDATOR OUTPUT:")
    print(f"Primary Category: {classification['primary_category']}")
    print(f"Client Suggested: {client_category}")
    print(f"Overridden: {'Yes' if classification['primary_category'] != client_category else 'No'}")
    print(f"Confidence: {classification['confidence']}")
    print(f"Reasoning: {classification['reasoning']}")
    print()
    print("=" * 60)

    if classification['primary_category'] != client_category:
        print(f"✅ Category correctly overridden from '{client_category}' to '{classification['primary_category']}'")
    else:
        print(f"ℹ️  Category kept as suggested: '{client_category}'")


if __name__ == "__main__":
    print("\n🧪 Testing Priority & Category Integration\n")

    try:
        test_architect_priority()
        test_validator_category()
        print("\n✅ All tests passed!\n")
    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback
        traceback.print_exc()

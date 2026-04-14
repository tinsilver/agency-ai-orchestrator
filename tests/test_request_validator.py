from dotenv import load_dotenv
load_dotenv()

from langfuse import observe, get_client
from app.agents.request_validator import RequestValidatorAgent
from app.domain.evaluator import LightweightValidator


@observe(name="test-request-validator")
def run_tests():
    langfuse = get_client()
    langfuse.update_current_trace(
        session_id="test-request-validator",
        user_id="test-user",
        tags=["test", "request-validator"],
    )

    agent = RequestValidatorAgent()
    validator = LightweightValidator()

    sample_context = {
        "Client Name": "acmeplumbing.com",
        "Tech Stack": "WordPress, Elementor",
        "Brand Guidelines": "Blue/white, professional tone",
    }

    # Test 1: Complete blog post request
    print("--- Test 1: Complete blog post request ---")
    result = agent.validate_and_classify(
        request="Write a 1500-word blog post about '10 Signs You Need Emergency Plumbing' targeting the keyword 'emergency plumber near me'",
        client_context=sample_context,
    )
    validator.report_usage(result["usage"], result["model"])
    c = result["content"]
    print(f"  Category: {c['primary_category']}")
    print(f"  Complete: {c['complete']}")
    print(f"  Confidence: {c['confidence']}")
    print(f"  Missing: {c['missing']}")
    print(f"  Reasoning: {c['reasoning']}")

    # Test 2: Vague bug report (incomplete)
    print("\n--- Test 2: Vague bug report ---")
    result = agent.validate_and_classify(
        request="The contact form isn't working",
        client_context=sample_context,
    )
    validator.report_usage(result["usage"], result["model"])
    c = result["content"]
    print(f"  Category: {c['primary_category']}")
    print(f"  Complete: {c['complete']}")
    print(f"  Missing: {c['missing']}")
    print(f"  Reasoning: {c['reasoning']}")

    # Test 3: Multi-category request (new page + SEO)
    print("\n--- Test 3: Multi-category request ---")
    result = agent.validate_and_classify(
        request="Create a new Services page listing all our plumbing services, and make sure it ranks for 'plumbing services in Austin'",
        client_context=sample_context,
    )
    validator.report_usage(result["usage"], result["model"])
    c = result["content"]
    print(f"  Category: {c['primary_category']}")
    print(f"  Subcategories: {c['subcategories']}")
    print(f"  Complete: {c['complete']}")
    print(f"  Missing: {c['missing']}")
    print(f"  Reasoning: {c['reasoning']}")

    # Test 4: Greeting only (unclear, incomplete)
    print("\n--- Test 4: Greeting only ---")
    result = agent.validate_and_classify(
        request="Hi there, thanks!",
        client_context=sample_context,
    )
    validator.report_usage(result["usage"], result["model"])
    c = result["content"]
    print(f"  Category: {c['primary_category']}")
    print(f"  Complete: {c['complete']}")
    print(f"  Confidence: {c['confidence']}")
    print(f"  Reasoning: {c['reasoning']}")

    trace_id = langfuse.get_current_trace_id()
    return trace_id


if __name__ == "__main__":
    trace_id = run_tests()
    langfuse = get_client()
    langfuse.flush()
    trace_url = langfuse.get_trace_url(trace_id=trace_id)
    print(f"\n--- Done! View trace: {trace_url} ---")

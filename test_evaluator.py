from dotenv import load_dotenv
load_dotenv()

from langfuse import observe, get_client
from app.domain.evaluator import LightweightValidator

@observe(name="test-evaluator")
def run_test():
    langfuse = get_client()
    langfuse.update_current_trace(
        session_id="test-evaluator",
        user_id="test-user",
        tags=["test", "evaluator"],
    )

    validator = LightweightValidator()

    # Test 1: Good request with a structured plan
    print("--- Test 1: Good request + structured plan ---")
    scores = validator.validate(
        request_text="Add a contact form below the hero section on the homepage",
        plan=(
            "## 📝 Task Summary\n"
            "Add a contact form component below the hero.\n\n"
            "## 📋 Execution Steps\n"
            "1. Create form component\n"
            "2. Add validation\n"
            "3. Style to match brand\n"
        ),
    )
    for name, value in scores.items():
        print(f"  {name}: {value}")

    # Test 2: Greeting-only request (should fail several checks)
    print("\n--- Test 2: Greeting-only request ---")
    scores = validator.validate(request_text="hello")
    for name, value in scores.items():
        print(f"  {name}: {value}")

    # Test 3: Short request without action verb
    print("\n--- Test 3: Short vague request ---")
    scores = validator.validate(request_text="the logo")
    for name, value in scores.items():
        print(f"  {name}: {value}")

    # Test 4: Plan missing structure
    print("\n--- Test 4: Plan without required sections ---")
    scores = validator.validate(
        request_text="Build a new landing page for the product launch",
        plan="Just make it look nice and modern.",
    )
    for name, value in scores.items():
        print(f"  {name}: {value}")

    trace_id = langfuse.get_current_trace_id()
    return trace_id

if __name__ == "__main__":
    trace_id = run_test()
    langfuse = get_client()
    langfuse.flush()
    trace_url = langfuse.get_trace_url(trace_id=trace_id)
    print(f"\n--- Done! View trace: {trace_url} ---")

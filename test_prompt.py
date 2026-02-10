import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.agents.architect import ArchitectAgent

async def test_architect_prompt_compilation():
    """Test that prompt variables compile correctly"""
    agent = ArchitectAgent()
    
    result = agent.generate_plan(
        request="Create a contact form",
        client_context={"brand": "Test Co"},
        file_summaries=None,
        website_content="Homepage with navigation"
    )

    import json
    print("\n--- Result ---")
    print(json.dumps(result["content"], indent=2))
    print(f"\nModel: {result['model']}")

if __name__ == "__main__":
    asyncio.run(test_architect_prompt_compilation())

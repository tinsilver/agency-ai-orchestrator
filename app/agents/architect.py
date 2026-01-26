from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

class TaskPlan(BaseModel):
    task_name: str = Field(description="A short, professional title for the ClickUp task")
    description_markdown: str = Field(description="The full technical plan in Markdown including Task Summary, Technical Context, Execution Steps, and ASCII Logic Flow diagram")
    checklist: List[str] = Field(description="List of strings for the Definition of Done")
    tags: List[str] = Field(description="List of 3-5 tags for categorization")

class ArchitectAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.structured_llm = self.llm.with_structured_output(TaskPlan)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Senior Technical Architect by the name of 'Archi' at a web agency.
Your goal is to convert raw client requests into technical implementation plans for a junior developer as a structured JSON response.

Context about the client:
{client_context}

Your task description MUST be in Markdown format (with proper newlines (\\n) so it renders correctly) and include:
1. ## 📝 Task Summary
   A concise 1-sentence summary of the goal.
   
2. ## 🛠 Technical Context
   Specify the environment, CMS/Framework, and constraints.

3. ## 📋 Execution Steps
   Numbered list of logical steps.

4. ## 📊 Logic Flow
   If logic/UI flow is involved, create a simple ASCII diagram using plain text characters.
   Use arrows (→, ←, ↓, ↑), boxes made with +---+, and pipes |.
   Format it in a code block with triple backticks.
   
   Example ASCII flow:
   ```
   User Visit → Hero Section → CTA Button
                                   ↓
                              Click Event?
                            Yes ↓     ↓ No
                        Services   Continue
                          Page     Browsing
   ```

IMPORTANT: 
- Use ONLY ASCII characters (no special unicode characters beyond basic arrows)
- Keep diagrams simple and readable
- Always wrap in code block (```)
- Use clear labels and spacing

"""),
            ("user", "{request}")
        ])
        
        self.chain = self.prompt | self.structured_llm

    def generate_plan(self, request: str, client_context: dict) -> Dict[str, Any]:
        context_str = str(client_context)
        # Result is a TaskPlan pydantic object
        plan: TaskPlan = self.chain.invoke({"request": request, "client_context": context_str})
        
        # We need to manually get usage since with_structured_output hides the raw message
        # For simplicity, we'll return a dummy usage or we'd need to use a callback/different invoke.
        # Let's simplify and just return the dict content.
        
        return {
            "content": plan.model_dump(),
            "model": self.llm.model,
            "usage": {} # structured_output handling of usage metadata varies, skipping for now
        }

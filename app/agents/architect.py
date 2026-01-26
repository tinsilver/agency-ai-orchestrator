from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

class TaskPlan(BaseModel):
    task_name: str = Field(description="A short, professional title for the ClickUp task")
    description_markdown: str = Field(description="The full technical plan in Markdown (Task Summary, Technical Context, Execution Steps, Mermaid diagram)")
    checklist: List[str] = Field(description="List of strings for the Definition of Done")
    tags: List[str] = Field(description="List of 3-5 tags for categorization")
    mermaid_code: str = Field(description="Valid Mermaid flowchart TD syntax ONLY. No ASCII arrows.")

class ArchitectAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.structured_llm = self.llm.with_structured_output(TaskPlan)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Senior Technical Architect at a web agency.
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

4. ## 📊 Logic Flow (Mermaid)
   If logic/UI flow is involved, include a Mermaid.js diagram. Every Mermaid diagram MUST start exactly with ```mermaid and the first line must a mermaid diagram type (e.g. flowchart TD, graph TD). Use standard Mermaid connectors --> and never use ASCII arrows like ↓. Ensure there is a double newline before the mermaid block. Always wrap labels in quotes: `A["Label with & symbol"]`. (Also put the raw code in the mermaid_code field).

For the 'mermaid_graph' field:
- Use ONLY valid Mermaid.js syntax.
- Start with 'flowchart TD'.
- Use standard node definitions like A["Text"] --> B["Text"].
- NEVER use ASCII arrows (↓) or plain text diagrams.

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

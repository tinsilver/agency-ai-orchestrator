from typing import Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class ReviewAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a QA Lead. Review the following Technical Plan and Mermaid diagram.
            
Criteria for APPROVAL:
1. Mermaid diagram syntax is valid (no obvious syntax errors).
2. Technical specs cover all parts of the client request.
3. Steps are clear and actionable.

Client Request: {request}

If the plan is good, output ONLY the word "APPROVE".
If not, output a concise critique explaining what needs to be fixed. Do not generate a new plan, just the critique.
"""),
            ("user", "{plan}")
        ])
        
        # Removed StrOutputParser
        self.chain = self.prompt | self.llm

    def review_plan(self, request: str, plan: str) -> Dict[str, Any]:
        response = self.chain.invoke({"request": request, "plan": plan})
        return {
            "content": response.content,
            "model": self.llm.model,
            "usage": response.response_metadata.get("usage", {})
        }

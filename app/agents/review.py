from typing import Dict, Any
from langchain_anthropic import ChatAnthropic
from langfuse import observe
from langfuse.langchain import CallbackHandler
from app.domain.prompt_manager import PromptManager

class ReviewAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.prompt_manager = PromptManager()

    @observe(name="qa-review-plan")
    def review_plan(self, request: str, plan: str) -> Dict[str, Any]:
        # Fetch and compile prompt
        prompt = self.prompt_manager.get_prompt("qa-review-agent")
        chat_prompt = self.prompt_manager.compile_to_langchain(prompt, {
            "request": request,
            "plan": plan,
        })

        chain = chat_prompt | self.llm

        # Execute
        langfuse_handler = CallbackHandler()
        response = chain.invoke(
            {},
            config={"callbacks": [langfuse_handler]}
        )

        return {
            "content": response.content,
            "model": self.llm.model,
            "usage": response.response_metadata.get("usage", {})
        }

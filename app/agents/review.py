from typing import Dict, Any
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langfuse import Langfuse, observe
from langfuse.langchain import CallbackHandler

class ReviewAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.langfuse = Langfuse()
        self._prompt_cache = None
        self._prompt_cache_time = None
        self._cache_ttl = 300  # 5 minutes

    def _get_prompt(self):
        import time
        current_time = time.time()
        
        if (self._prompt_cache is None or 
            self._prompt_cache_time is None or 
            current_time - self._prompt_cache_time > self._cache_ttl):
            
            self._prompt_cache = self.langfuse.get_prompt("qa-review-agent", label="production")
            self._prompt_cache_time = current_time
        
        return self._prompt_cache

    @observe(name="qa-review-plan")
    def review_plan(self, request: str, plan: str) -> Dict[str, Any]:
        # Fetch prompt from Langfuse
        prompt = self._get_prompt()
        
        # Compile prompt with variables
        compiled_prompt = prompt.compile(
            request=request,
            plan=plan
        )
        
        # Convert to LangChain format
        messages = [
            (msg["role"], msg["content"]) 
            for msg in compiled_prompt
        ]
        
        chat_prompt = ChatPromptTemplate.from_messages(messages)
        chain = chat_prompt | self.llm
        
        # Execute
        langfuse_handler = CallbackHandler()
        response = chain.invoke(
            {},  # Variables already compiled into the prompt
            config={"callbacks": [langfuse_handler]}
        )
        
        return {
            "content": response.content,
            "model": self.llm.model,
            "usage": response.response_metadata.get("usage", {})
        }
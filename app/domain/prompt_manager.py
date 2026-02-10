from typing import Dict, Any
from langfuse import Langfuse
import time


class PromptManager:
    """Domain service for managing LLM prompts via Langfuse"""

    def __init__(self, cache_ttl: int = 300):
        self.langfuse = Langfuse()
        self._cache: Dict[str, Any] = {}
        self._cache_times: Dict[str, float] = {}
        self._cache_ttl = cache_ttl

    def get_prompt(self, prompt_name: str, label: str = "production"):
        """Fetch prompt with automatic caching"""
        cache_key = f"{prompt_name}:{label}"
        current_time = time.time()

        if (cache_key not in self._cache or
            current_time - self._cache_times.get(cache_key, 0) > self._cache_ttl):

            self._cache[cache_key] = self.langfuse.get_prompt(prompt_name, label=label)
            self._cache_times[cache_key] = current_time

        return self._cache[cache_key]

    def compile_to_langchain(self, prompt, variables: Dict[str, Any]):
        """Compile Langfuse prompt to LangChain ChatPromptTemplate"""
        from langchain_core.prompts import ChatPromptTemplate

        compiled = prompt.compile(**variables)
        messages = [(msg["role"], msg["content"]) for msg in compiled]
        return ChatPromptTemplate.from_messages(messages)

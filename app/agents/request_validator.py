from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler
from app.domain.prompt_manager import PromptManager
from app.domain.request_category import RequestCategory


class ClassificationResult(BaseModel):
    primary_category: str = Field(description="The primary category from the valid categories list")
    subcategories: List[str] = Field(default_factory=list, description="Any additional applicable categories")
    complete: bool = Field(description="Whether the request has enough detail to create a technical specification")
    missing: List[str] = Field(default_factory=list, description="Specific information that is missing, as questions to ask the client")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")
    reasoning: str = Field(description="Brief explanation of the classification decision")


class RequestValidatorAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.structured_llm = self.llm.with_structured_output(ClassificationResult, include_raw=True)
        self.prompt_manager = PromptManager()

    @observe(name="validate-and-classify-request")
    def validate_and_classify(
        self,
        request: str,
        client_context: dict,
        file_summaries: list = None,
        website_content: str = None,
    ) -> Dict[str, Any]:
        context_str = str(client_context)

        website_context = ""
        if website_content:
            website_context = f"Website structure and content available:\n{website_content}"

        file_context = self._format_file_context(file_summaries)

        prompt = self.prompt_manager.get_prompt("request-validator-classifier")
        compiled = prompt.compile(
            request=request,
            client_context=context_str,
            file_context=file_context if file_context else "No files attached.",
            website_context=website_context if website_context else "No website data available.",
        )

        # Build messages directly to avoid LangChain re-parsing curly braces
        # (the system prompt and compiled context contain JSON/dict literals)
        role_map = {"system": SystemMessage, "user": HumanMessage}
        messages = [role_map.get(m["role"], HumanMessage)(content=m["content"]) for m in compiled]

        langfuse_handler = CallbackHandler()
        result = self.structured_llm.invoke(
            messages,
            config={"callbacks": [langfuse_handler]}
        )

        # Handle parsing error fallback
        if result.get("parsing_error"):
            classification = ClassificationResult(
                primary_category=RequestCategory.UNCLEAR,
                subcategories=[],
                complete=False,
                missing=["Could not parse the request — needs manual review"],
                confidence=0.0,
                reasoning=f"Parsing error: {result['parsing_error']}",
            )
        else:
            classification = result["parsed"]

        # Validate category is in our known list
        if classification.primary_category not in RequestCategory.ALL:
            classification.primary_category = RequestCategory.UNCLEAR

        usage = result["raw"].response_metadata.get("usage", {})

        return {
            "content": classification.model_dump(),
            "model": self.llm.model,
            "usage": usage,
        }

    def _format_file_context(self, file_summaries: Optional[list]) -> str:
        if not file_summaries:
            return ""

        parts = []
        for fs in file_summaries:
            if fs.get("error"):
                parts.append(f"- File error: {fs['error']}")
            else:
                filename = fs.get("filename", "unknown")
                file_type = fs.get("type", "unknown")
                content = fs.get("extracted_content") or ""
                preview = content[:500] + "..." if len(content) > 500 else content
                parts.append(f"- {filename} ({file_type}): {preview}")

        return "\n".join(parts)

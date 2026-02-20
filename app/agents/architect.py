from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langfuse import observe
from langfuse.langchain import CallbackHandler
from app.domain.prompt_manager import PromptManager

class TaskPlan(BaseModel):
    task_name: str = Field(description="A short, professional title for the ClickUp task")
    description_markdown: str = Field(description="The full technical plan in Markdown including Task Summary, Technical Context, Execution Steps, and ASCII Logic Flow diagram")
    checklist: List[str] = Field(description="List of strings for the Definition of Done")
    tags: List[str] = Field(description="List of 3-5 tags for categorization")
    priority: str = Field(description="Final task priority: Low, Normal, High, or Urgent (considering client input and context)")
    priority_reasoning: str = Field(description="Brief explanation of why this priority was chosen")

class ArchitectAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.structured_llm = self.llm.with_structured_output(TaskPlan, include_raw=True)
        self.prompt_manager = PromptManager()

    @observe(name="architect-generate-plan")
    def generate_plan(self, request: str, client_context: dict, client_priority: str = None, request_category: str = None, file_summaries: list = None, website_content: str = None, dynamic_context: dict = None) -> Dict[str, Any]:
        context_str = str(client_context)

        # Format website content if available
        website_context = ""
        if website_content:
             website_context = f"\n\n## 🌐 Existing Website Context\nUse this information to respect the current layout and structure:\n\n{website_content}\n"

        # Format dynamic enrichment context if available
        enrichment_context = ""
        if dynamic_context:
            enrichment_context = "\n\n## 🔍 Additional Context from Enrichment\nThe following information was discovered through automated research:\n\n"
            for key, value in dynamic_context.items():
                if isinstance(value, dict):
                    answer = value.get("answer", value)
                    source = value.get("source", "unknown")
                    confidence = value.get("confidence", 0)
                    enrichment_context += f"- **{key.replace('_', ' ').title()}**: {answer} _(source: {source}, confidence: {confidence:.2f})_\n"
                else:
                    enrichment_context += f"- **{key.replace('_', ' ').title()}**: {value}\n"
            enrichment_context += "\nUse this enriched context to inform your technical plan where relevant.\n"

        # Format file content if available
        file_context = ""
        if file_summaries:
            file_context = "\n\n## 📎 Attached Files\nThe client has attached the following files:\n\n"
            for file_summary in file_summaries:
                if file_summary.get("error"):
                    file_context += f"- ❌ Error: {file_summary['error']}\n"
                else:
                    filename = file_summary.get('filename', 'unknown')
                    file_type = file_summary.get('type', 'unknown')
                    content = file_summary.get('extracted_content', '')

                    file_context += f"### File: {filename} ({file_type})\n"
                    if content:
                        file_context += f"```\n{content[:1000]}{'...' if len(content) > 1000 else ''}\n```\n\n"
                    else:
                        file_context += "(No text content extracted)\n\n"

        # Fetch and compile prompt
        prompt = self.prompt_manager.get_prompt("architect-agent")
        chat_prompt = self.prompt_manager.compile_to_langchain(prompt, {
            "request": request,
            "client_context": context_str,
            "client_priority": client_priority or "not specified",
            "request_category": request_category or "unclear",
            "file_context": file_context,
            "website_context": website_context,
            "enrichment_context": enrichment_context,  # NEW
        })

        chain = chat_prompt | self.structured_llm

        # Execute
        langfuse_handler = CallbackHandler()
        result = chain.invoke(
            {},
            config={"callbacks": [langfuse_handler]}
        )

        plan: TaskPlan = result["parsed"]
        usage = result["raw"].response_metadata.get("usage", {})

        return {
            "content": plan.model_dump(),
            "model": self.llm.model,
            "usage": usage
        }

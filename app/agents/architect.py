from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langfuse import observe
from langfuse import get_client
from langfuse.langchain import CallbackHandler
import os

class TaskPlan(BaseModel):
    task_name: str = Field(description="A short, professional title for the ClickUp task")
    description_markdown: str = Field(description="The full technical plan in Markdown including Task Summary, Technical Context, Execution Steps, and ASCII Logic Flow diagram")
    checklist: List[str] = Field(description="List of strings for the Definition of Done")
    tags: List[str] = Field(description="List of 3-5 tags for categorization")

class ArchitectAgent:
    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.structured_llm = self.llm.with_structured_output(TaskPlan)
        self.langfuse = langfuse = get_client()
        
        # Verify connection
        if langfuse.auth_check():
            print("Langfuse client is authenticated and ready!")
        else:
            print("Authentication failed. Please check your credentials and host.")

        self._prompt_cache = None
        self._prompt_cache_time = None
        self._cache_ttl = 300  # 5 minutes
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an Expert Agency Architect and SEO Specialist. 
            
            Your goal is to break down a client request into a detailed, step-by-step Technical Plan that a developer can execute.
            
            # Roles & Responsibilities
            1. **Architect**: Design the technical solution, component structure, and logic flow.
            2. **SEO Specialist**: If the request involves **New Pages** or **Copywriting**, you MUST perform an SEO Analysis relative to the client's existing `website_context`.

            # Inputs to Analyze
            - **Client Context**: Brand guidelines, tech stack, and preferences.
            - **File Attachments**: Spec documents or wireframes (if provided).
            - **Website Context**: Existing structure, navigation, and content (scraped data).

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
            5. **Checklist**: A definition of done (DoD) list.
            6. **Tags**: List of relevant tags (e.g. "wordpress", "python", "agency-ai").

            # SEO Analysis Requirements (CONDITIONAL)
            IF the request involves creating a NEW PAGE or writing/editing TEXT COPY:
            - You MUST add a `## 🔍 SEO & Metadata` section to the description_markdown.
            - This section MUST include:
            - **Target Keyword Strategy**: Based on page topic.
            - **Recommended Title Tag**: Format: `[Page Topic] | [Brand Name]`.
            - **Meta Description**: Compelling summary (< 160 chars).
            - **URL Slug**: e.g. `/careers/senior-developer`.
            - **Schema Markup**: Recommend specific JSON-LD schemas (e.g. `JobPosting`, `Article`, `Service`).
            - **GSC Action**: "Request indexing in Google Search Console after publish."

            IMPORTANT: 
            - Use ONLY ASCII characters (no special unicode characters beyond basic arrows)
            - Keep diagrams simple and readable
            - Always wrap in code block (```)
            - Use clear labels and spacing

            {file_context}

            {website_context}
            """),
            ("user", "{request}")
        ])
        
        self.chain = self.prompt | self.structured_llm
    
    def _get_prompt(self):
        import time
        current_time = time.time()
    
        if (self._prompt_cache is None or 
            self._prompt_cache_time is None or 
            current_time - self._prompt_cache_time > self._cache_ttl):
        
            self._prompt_cache = self.langfuse.get_prompt("architect-agent", label="production")
            self._prompt_cache_time = current_time
    
        return self._prompt_cache

    @observe(name="architect-generate-plan")
    def generate_plan(self, request: str, client_context: dict, file_summaries: list = None, website_content: str = None) -> Dict[str, Any]:
        context_str = str(client_context)
        
        # Format website content if available
        website_context = ""
        if website_content:
             website_context = f"\n\n## 🌐 Existing Website Context\nUse this information to respect the current layout and structure:\n\n{website_content}\n"
        
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
        else:
            file_context = ""
        
        # Fetch prompt from Langfuse
        prompt = self._get_prompt()
        
        # Compile prompt with variables
        compiled_prompt = prompt.compile(
            request=request,
            client_context=context_str,
            file_context=file_context,
            website_context=website_context
        )
        
        # Convert to LangChain format
        messages = [
            (msg["role"], msg["content"]) 
            for msg in compiled_prompt
        ]
        
        from langchain_core.prompts import ChatPromptTemplate
        chat_prompt = ChatPromptTemplate.from_messages(messages)
        chain = chat_prompt | self.structured_llm
        
        # Execute
        langfuse_handler = CallbackHandler()
        plan: TaskPlan = chain.invoke(
            {}, # Variables already compiled into the prompt
            config={"callbacks": [langfuse_handler]}
        )
        
        return {
            "content": plan.model_dump(),
            "model": self.llm.model,
            "usage": {}
        }

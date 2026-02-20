"""
DynamicEnrichmentAgent: Gathers missing information using tools.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langfuse import observe
from langfuse.langchain import CallbackHandler

from app.domain.prompt_manager import PromptManager
from app.domain.enrichment_models import (
    EnrichmentResult, EnrichmentPlan, ToolAction, GatheredInformation
)
from app.services.enrichment_toolkit import EnrichmentToolkit


class DynamicEnrichmentAgent:
    """
    Agent that attempts to gather missing information using available tools.

    Three-phase process:
    1. Planning: Decide which tools to use for which questions
    2. Execution: Run the tools and collect results
    3. Synthesis: Extract answers from tool results
    """

    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.structured_llm = self.llm.with_structured_output(EnrichmentPlan, include_raw=True)
        self.prompt_manager = PromptManager()
        self.toolkit = EnrichmentToolkit()

    @observe(name="dynamic-enrichment-agent")
    async def gather_context(
        self,
        missing_information: List[str],
        raw_request: str,
        static_context: dict,
        website_url: Optional[str],
        website_content: Optional[str],
        tool_usage_stats: dict,
        previous_findings: Optional[Dict[str, Any]] = None
    ) -> EnrichmentResult:
        """
        Attempt to gather missing information using available tools.

        Args:
            missing_information: List of questions that need answers
            raw_request: Original client request text
            static_context: Context from ClickUp/static sources
            website_url: Client's website URL
            website_content: Scraped website content
            tool_usage_stats: Current tool usage statistics (for budget enforcement)
            previous_findings: Information gathered in previous iterations

        Returns:
            EnrichmentResult with gathered information and metadata
        """
        if not missing_information:
            # No questions to answer
            return EnrichmentResult(
                gathered_info=[],
                tools_used=[],
                tokens_used=0,
                questions_answered=0,
                questions_total=0,
                confidence=1.0,
                errors=[]
            )

        # Phase 1: Create enrichment plan
        plan = await self._create_plan(
            missing_information,
            raw_request,
            static_context,
            website_url,
            website_content,
            tool_usage_stats
        )

        # Check if planning failed
        if not plan or not plan.actions:
            return EnrichmentResult(
                gathered_info=[],
                tools_used=[],
                tokens_used=0,
                questions_answered=0,
                questions_total=len(missing_information),
                confidence=0.0,
                errors=["Failed to create enrichment plan"]
            )

        # Phase 2: Execute tools
        gathered_info, tools_used, errors = await self._execute_tools(plan, tool_usage_stats)

        # Phase 3: Calculate metrics
        questions_answered = len([info for info in gathered_info if info.answer])
        confidence = self._calculate_confidence(gathered_info, missing_information)

        # Estimate token usage (rough approximation)
        # Planning used some tokens, tool execution may have used some for synthesis
        tokens_used = self._estimate_tokens_used(plan, gathered_info)

        return EnrichmentResult(
            gathered_info=gathered_info,
            tools_used=tools_used,
            tokens_used=tokens_used,
            questions_answered=questions_answered,
            questions_total=len(missing_information),
            confidence=confidence,
            errors=errors
        )

    @observe(name="create-enrichment-plan")
    async def _create_plan(
        self,
        missing_information: List[str],
        raw_request: str,
        static_context: dict,
        website_url: Optional[str],
        website_content: Optional[str],
        tool_usage_stats: dict
    ) -> Optional[EnrichmentPlan]:
        """
        Phase 1: Create a plan for which tools to use.

        Args:
            missing_information: Questions to answer
            raw_request: Original request
            static_context: Static context
            website_url: Client's website URL
            website_content: Website content
            tool_usage_stats: Tool usage stats

        Returns:
            EnrichmentPlan or None if planning fails
        """
        try:
            # Get planning prompt from Langfuse
            prompt = self.prompt_manager.get_prompt("dynamic-enrichment-planner")

            # Format tool budgets for the prompt
            available_tools = self._format_available_tools(tool_usage_stats)

            # Compile prompt with variables
            compiled = prompt.compile(
                missing_information="\n".join(f"- {q}" for q in missing_information),
                raw_request=raw_request,
                static_context=str(static_context)[:500],  # Truncate to avoid bloat
                website_url=website_url or static_context.get("Website URL", "unknown"),
                available_tools=available_tools
            )

            # Build messages
            role_map = {"system": SystemMessage, "user": HumanMessage}
            messages = [role_map.get(m["role"], HumanMessage)(content=m["content"]) for m in compiled]

            # Invoke LLM with structured output
            langfuse_handler = CallbackHandler()
            result = self.structured_llm.invoke(
                messages,
                config={"callbacks": [langfuse_handler]}
            )

            # Handle parsing errors
            if result.get("parsing_error"):
                return None

            plan = result["parsed"]
            return plan

        except Exception as e:
            print(f"Error creating enrichment plan: {e}")
            return None

    @observe(name="execute-enrichment-tools")
    async def _execute_tools(
        self,
        plan: EnrichmentPlan,
        tool_usage_stats: dict
    ) -> tuple[List[GatheredInformation], List[str], List[str]]:
        """
        Phase 2: Execute the planned tool calls.

        Args:
            plan: Enrichment plan
            tool_usage_stats: Tool usage statistics

        Returns:
            Tuple of (gathered_info, tools_used, errors)
        """
        gathered_info = []
        tools_used = []
        errors = []

        for action in plan.actions:
            try:
                # Call the tool via toolkit
                result = await self.toolkit.call_tool(
                    action.tool,
                    action.params,
                    tool_usage_stats
                )

                # Check for errors
                if result.get("error"):
                    errors.append(f"{action.tool}: {result['error']}")
                    # Still add to gathered_info but with no answer
                    gathered_info.append(GatheredInformation(
                        question=action.question,
                        answer=None,
                        source=action.tool,
                        source_url=action.params.get("url"),
                        confidence=0.0,
                        raw_data=result
                    ))
                    continue

                # Extract answer from result
                answer_info = self._extract_answer_from_result(
                    action.question,
                    action.tool,
                    result,
                    action.params
                )

                gathered_info.append(answer_info)
                tools_used.append(action.tool)

            except Exception as e:
                errors.append(f"{action.tool} failed: {str(e)}")
                gathered_info.append(GatheredInformation(
                    question=action.question,
                    answer=None,
                    source=action.tool,
                    source_url=None,
                    confidence=0.0,
                    raw_data={"error": str(e)}
                ))

        return gathered_info, list(set(tools_used)), errors

    def _extract_answer_from_result(
        self,
        question: str,
        tool: str,
        result: Dict[str, Any],
        params: Dict[str, Any]
    ) -> GatheredInformation:
        """
        Extract a structured answer from tool result.
        Uses heuristics to find the relevant information.

        Args:
            question: The question being answered
            tool: Tool that was used
            result: Raw tool result
            params: Parameters passed to tool

        Returns:
            GatheredInformation object
        """
        question_lower = question.lower()

        # Tool-specific extraction logic
        if tool == "form_detector":
            # Check if form was found
            forms_found = result.get("forms_found", 0)
            if forms_found > 0:
                forms = result.get("forms", [])
                # Extract contact form info
                contact_forms = [f for f in forms if f.get("type") == "contact"]
                if contact_forms:
                    answer = f"Contact form found with fields: {', '.join(f['name'] for f in contact_forms[0]['fields'])}"
                else:
                    answer = f"{forms_found} form(s) found on page"
                confidence = 0.8
            else:
                answer = "No forms found on this page"
                confidence = 0.3

            return GatheredInformation(
                question=question,
                answer=answer,
                source=tool,
                source_url=params.get("url"),
                confidence=confidence,
                raw_data=result
            )

        elif tool == "social_media_finder":
            accounts = result.get("accounts", {})
            found = {k: v for k, v in accounts.items() if v is not None}
            if found:
                answer = f"Found: {', '.join(f'{k}: {v}' for k, v in found.items())}"
                confidence = result.get("confidence", 0.7)
            else:
                answer = "No social media accounts found"
                confidence = 0.2

            return GatheredInformation(
                question=question,
                answer=answer,
                source=tool,
                source_url=params.get("url"),
                confidence=confidence,
                raw_data=result
            )

        elif tool == "seo_audit":
            # Extract relevant SEO info based on question
            if "meta" in question_lower or "description" in question_lower:
                meta = result.get("meta_tags", {})
                answer = f"Meta description: {meta.get('description', 'Not found')}"
                confidence = 0.8 if meta.get('has_description') else 0.3
            elif "keyword" in question_lower:
                meta = result.get("meta_tags", {})
                keywords = meta.get("keywords", "None specified")
                answer = f"Keywords: {keywords}"
                confidence = 0.6
            else:
                score = result.get("score", 0)
                issues = result.get("issues", [])
                answer = f"SEO score: {score}/100. Issues: {len(issues)}"
                confidence = 0.7

            return GatheredInformation(
                question=question,
                answer=answer,
                source=tool,
                source_url=params.get("url"),
                confidence=confidence,
                raw_data=result
            )

        elif tool == "web_search":
            # Extract from search results
            results_list = result.get("results", [])
            if results_list:
                top_result = results_list[0]
                answer = f"{top_result.get('title', '')}: {top_result.get('snippet', '')}"
                confidence = 0.6 if not result.get("is_mock") else 0.4
            else:
                answer = "No search results found"
                confidence = 0.2

            return GatheredInformation(
                question=question,
                answer=answer,
                source=tool,
                source_url=results_list[0].get("url") if results_list else None,
                confidence=confidence,
                raw_data=result
            )

        elif tool == "pdf_extract":
            # Extract colors, fonts, or general content
            if "color" in question_lower:
                colors = result.get("colors", [])
                answer = f"Colors found: {', '.join(colors)}" if colors else "No colors found"
                confidence = 0.8 if colors else 0.3
            elif "font" in question_lower:
                fonts = result.get("fonts", [])
                answer = f"Fonts: {', '.join(fonts)}" if fonts else "No fonts identified"
                confidence = 0.7 if fonts else 0.3
            else:
                text_length = result.get("text_length", 0)
                answer = f"PDF contains {text_length} characters of text"
                confidence = 0.6

            return GatheredInformation(
                question=question,
                answer=answer,
                source=tool,
                source_url=None,
                confidence=confidence,
                raw_data=result
            )

        elif tool == "google_maps_scraper":
            # Extract business info
            if "hour" in question_lower or "open" in question_lower:
                hours = result.get("hours", {})
                answer = f"Hours: {hours}" if hours else "Hours not found"
                confidence = 0.5 if result.get("is_mock") else 0.8
            elif "phone" in question_lower:
                phone = result.get("phone", "Not found")
                answer = f"Phone: {phone}"
                confidence = 0.5 if result.get("is_mock") else 0.8
            else:
                address = result.get("address", "Not found")
                answer = f"Address: {address}"
                confidence = 0.5 if result.get("is_mock") else 0.8

            return GatheredInformation(
                question=question,
                answer=answer,
                source=tool,
                source_url=result.get("website"),
                confidence=confidence,
                raw_data=result
            )

        # Default: generic extraction
        else:
            # Try to extract any meaningful value
            if isinstance(result, dict):
                # Look for common answer fields
                answer = result.get("answer") or result.get("result") or str(result)[:200]
                confidence = 0.5
            else:
                answer = str(result)[:200]
                confidence = 0.3

            return GatheredInformation(
                question=question,
                answer=answer,
                source=tool,
                source_url=params.get("url"),
                confidence=confidence,
                raw_data=result
            )

    def _format_available_tools(self, tool_usage_stats: dict) -> str:
        """Format tool budget information for the planning prompt."""
        budgets = self.toolkit.tool_budgets
        lines = []

        for tool_name, max_calls in budgets.items():
            current_calls = tool_usage_stats.get(tool_name, {}).get("calls", 0)
            remaining = max_calls - current_calls
            status = "✓" if remaining > 0 else "✗"
            lines.append(f"{status} {tool_name}: {remaining}/{max_calls} calls remaining")

        return "\n".join(lines)

    def _calculate_confidence(
        self,
        gathered_info: List[GatheredInformation],
        missing_information: List[str]
    ) -> float:
        """
        Calculate overall confidence in enrichment results.

        Args:
            gathered_info: Information gathered
            missing_information: Original questions

        Returns:
            Confidence score 0.0-1.0
        """
        if not missing_information:
            return 1.0

        # Calculate based on:
        # 1. How many questions got answers
        # 2. Average confidence of those answers

        answers_with_content = [info for info in gathered_info if info.answer]
        answer_rate = len(answers_with_content) / len(missing_information)

        if answers_with_content:
            avg_confidence = sum(info.confidence for info in answers_with_content) / len(answers_with_content)
        else:
            avg_confidence = 0.0

        # Weighted combination
        overall_confidence = (answer_rate * 0.6) + (avg_confidence * 0.4)

        return round(overall_confidence, 2)

    def _estimate_tokens_used(
        self,
        plan: EnrichmentPlan,
        gathered_info: List[GatheredInformation]
    ) -> int:
        """
        Estimate tokens used in this enrichment iteration.

        Args:
            plan: The enrichment plan
            gathered_info: Gathered information

        Returns:
            Estimated token count
        """
        # Rough estimation:
        # - Planning: ~1000 tokens
        # - Each tool call synthesis: ~200 tokens
        planning_tokens = 1000
        synthesis_tokens = len(gathered_info) * 200

        return planning_tokens + synthesis_tokens

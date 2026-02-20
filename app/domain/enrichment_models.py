"""
Pydantic models for the recursive context-gathering enrichment system.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ToolAction(BaseModel):
    """Represents a single tool call action in the enrichment plan."""
    tool: str = Field(description="The tool to use (e.g., 'web_fetch', 'form_detector')")
    question: str = Field(description="The question this tool call aims to answer")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the tool call (e.g., {'url': 'https://example.com'})"
    )
    reasoning: str = Field(description="Why this tool was chosen for this question")


class EnrichmentPlan(BaseModel):
    """Structured plan for gathering missing information using tools."""
    actions: List[ToolAction] = Field(
        description="List of tool actions to execute"
    )
    total_estimated_tokens: int = Field(
        default=0,
        description="Estimated total tokens this plan will consume"
    )
    reasoning: str = Field(
        description="Overall strategy for this enrichment attempt"
    )


class GatheredInformation(BaseModel):
    """Represents information gathered from a single tool execution."""
    question: str = Field(description="The question that was being answered")
    answer: Optional[str] = Field(
        default=None,
        description="The answer found, or None if not found"
    )
    source: str = Field(description="Which tool provided this information")
    source_url: Optional[str] = Field(
        default=None,
        description="URL or identifier of the source data"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this answer (0.0-1.0)"
    )
    raw_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw data from the tool (for debugging/verification)"
    )


class EnrichmentResult(BaseModel):
    """Result of a complete enrichment attempt."""
    gathered_info: List[GatheredInformation] = Field(
        description="All information gathered in this iteration"
    )
    tools_used: List[str] = Field(
        description="List of tool names that were called"
    )
    tokens_used: int = Field(
        description="Total tokens consumed in this enrichment iteration"
    )
    questions_answered: int = Field(
        description="Number of questions successfully answered"
    )
    questions_total: int = Field(
        description="Total number of questions attempted"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence in the enrichment results"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Any errors encountered during enrichment"
    )

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of answered questions."""
        if self.questions_total == 0:
            return 0.0
        return self.questions_answered / self.questions_total

    def to_dynamic_context(self) -> Dict[str, Any]:
        """
        Convert gathered information to a flat dictionary for passing to architect.

        Returns:
            Dict mapping question keys to answer values.
        """
        context = {}
        for info in self.gathered_info:
            if info.answer:
                # Create a clean key from the question
                key = info.question.lower().replace(" ", "_").replace("?", "")
                context[key] = {
                    "answer": info.answer,
                    "source": info.source,
                    "confidence": info.confidence
                }
        return context


class EnrichmentIteration(BaseModel):
    """Represents a single iteration in the enrichment history."""
    iteration: int = Field(description="Iteration number (1-3)")
    questions_attempted: List[str] = Field(
        description="Questions we tried to answer in this iteration"
    )
    tools_used: List[str] = Field(
        description="Tools that were called"
    )
    information_found: Dict[str, Any] = Field(
        description="Information successfully gathered"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in this iteration's results"
    )
    tokens_used: int = Field(
        description="Tokens consumed in this iteration"
    )
    questions_resolved: int = Field(
        description="Number of questions resolved vs previous iteration"
    )
    stop_reason: Optional[str] = Field(
        default=None,
        description="If this was the last iteration, why did we stop?"
    )

"""
Eval 1: Input Validation (Binary Criteria Framework)
=====================================================
Runs when a request is first received (e.g. from Google Forms webhook).
Determines if the user's request is meaningful and actionable before
spending tokens/time on the full pipeline.

Framework (adapted from PRD Quality Gate course):
- Binary criteria: Each check is YES/NO (not Likert 1-5)
- Dimensional grouping: Criteria grouped into dimensions with thresholds
- Auto-fail conditions: Hard stops for dealbreaker inputs
- Evidence per criterion: Cite what you found (or didn't find)
- "Current State" + "Required Fix" per failed criterion

Returns:
    - is_valid (bool): Whether to proceed with the workflow
    - score (float): 0.0 to 1.0 confidence score (legacy, kept for API compat)
    - reason (str): Human-readable explanation of the decision
    - issues (list): Specific problems found (if any)
    - auto_fail_triggered (bool): Whether an auto-fail condition was hit
    - dimension_results (list): Per-dimension pass/fail with criteria detail
    - failed_criteria_fixes (list): "Current State" + "Required Fix" per failure
    - bar_raiser_decision (str): Final PASS/FAIL with reasoning
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate


# ---------------------------------------------------------------------------
# Auto-fail check
# ---------------------------------------------------------------------------

class AutoFailCheck(BaseModel):
    """A single auto-fail condition check."""
    condition: str = Field(description="Name of the auto-fail condition")
    triggered: bool = Field(description="True if this auto-fail was triggered (BAD)")
    evidence: str = Field(description="What you saw in the request that triggered or passed this check")


# ---------------------------------------------------------------------------
# Binary criterion (YES/NO with evidence)
# ---------------------------------------------------------------------------

class BinaryCriterion(BaseModel):
    """A single binary criterion evaluation — pass or fail, with evidence."""
    criterion_id: str = Field(description="ID like '1.1', '1.2', '2.1' etc.")
    criterion: str = Field(description="What is being checked")
    passed: bool = Field(description="True if the criterion is met (YES), False if not (NO)")
    evidence: str = Field(description="Cite what you found in the request that supports this judgment")
    current_state: str = Field(description="What the request currently says/has for this criterion")
    required_fix: str = Field(description="What the client needs to provide to pass. Empty string if passed.")


# ---------------------------------------------------------------------------
# Dimension result (group of criteria with threshold)
# ---------------------------------------------------------------------------

class DimensionResult(BaseModel):
    """Result for one evaluation dimension — a group of criteria with a pass threshold."""
    dimension_name: str = Field(description="Name of this dimension")
    criteria: List[BinaryCriterion] = Field(description="Individual criteria checks in this dimension")
    passed_count: int = Field(description="Number of criteria that passed")
    total_count: int = Field(description="Total number of criteria in this dimension")
    threshold: int = Field(description="Minimum criteria needed to pass this dimension")
    dimension_passed: bool = Field(description="True if passed_count >= threshold")


# ---------------------------------------------------------------------------
# Full evaluation result
# ---------------------------------------------------------------------------

class InputEvalResult(BaseModel):
    """Structured output from the input evaluator (Binary Criteria Framework)."""

    # Auto-fail checks
    auto_fail_checks: List[AutoFailCheck] = Field(
        description="Auto-fail condition checks — any trigger = immediate rejection"
    )
    auto_fail_triggered: bool = Field(
        description="True if ANY auto-fail condition was triggered"
    )

    # Dimensional binary criteria
    dimension_results: List[DimensionResult] = Field(
        description="Per-dimension evaluation results with binary criteria"
    )
    all_dimensions_passed: bool = Field(
        description="True only if ALL dimensions meet their threshold"
    )

    # Failed criteria with fixes (optimizer-style output)
    failed_criteria_fixes: List[Dict[str, str]] = Field(
        description="For each failed criterion: {'criterion_id': '...', 'criterion': '...', 'current_state': '...', 'required_fix': '...'}"
    )

    # Legacy fields (kept for backward compatibility with graph.py)
    is_valid: bool = Field(
        description="True if the request passes (all dimensions pass AND no auto-fails)"
    )
    score: float = Field(
        description="Confidence score from 0.0 to 1.0 — ratio of passed criteria to total"
    )
    category: str = Field(
        description="One of: 'actionable', 'vague', 'off_topic', 'gibberish', 'duplicate_likely', 'incomplete'"
    )
    reason: str = Field(
        description="One-sentence explanation of why this request was accepted or rejected"
    )
    issues: List[str] = Field(
        description="List of specific problems found. Empty list if none."
    )
    suggested_clarification: str = Field(
        description="If rejected or borderline, a question to send back to the client. Empty string if not needed."
    )

    # Bar Raiser decision
    bar_raiser_decision: str = Field(
        description="Final verdict: 'PASS — [reason]' or 'FAIL — [reason and what needs to change]'"
    )


class InputEvaluator:
    """
    Evaluates whether an incoming client request is meaningful enough
    to be processed by the full orchestrator pipeline.

    Uses the Binary Criteria Framework:
    - Auto-fail conditions (hard stops)
    - 3 dimensions with binary criteria and thresholds
    - Evidence per criterion
    - "Current State" + "Required Fix" per failure

    Use this BEFORE the enrichment node to save tokens and avoid
    creating junk tasks in ClickUp.
    """

    # Requests scoring below this threshold are rejected
    PASS_THRESHOLD = 0.4

    # --- Auto-Fail Conditions ---
    AUTO_FAIL_CONDITIONS = [
        "AF1: Request is empty, only whitespace, or fewer than 3 characters",
        "AF2: Request is clearly not related to web development, design, or digital services (e.g. 'what's the weather', 'tell me a joke')",
        "AF3: Request contains only greetings, pleasantries, or acknowledgments with zero task content (e.g. 'thanks', 'ok', 'hi there', 'just checking')",
    ]

    # --- Dimensions with Binary Criteria ---
    # Dimension 1: Intent Clarity (2 criteria, threshold 2/2)
    # Dimension 2: Scope Specificity (2 criteria, threshold 1/2)
    # Dimension 3: Feasibility Signal (2 criteria, threshold 1/2)

    DIMENSIONS = [
        {
            "name": "Intent Clarity",
            "threshold": 2,
            "criteria": [
                "1.1: Request contains an action verb or clear intent (add, change, fix, build, update, create, remove, redesign, improve, migrate, etc.)",
                "1.2: The desired outcome is understandable — you can tell WHAT the client wants even if details are sparse",
            ]
        },
        {
            "name": "Scope Specificity",
            "threshold": 1,
            "criteria": [
                "2.1: Request mentions a specific page, feature, component, section, or area of the site (e.g. 'About page', 'header', 'contact form', 'blog', 'checkout')",
                "2.2: Request provides enough context that a project manager could write a 1-sentence brief from it",
            ]
        },
        {
            "name": "Feasibility Signal",
            "threshold": 1,
            "criteria": [
                "3.1: Request is something a web development agency can realistically deliver (not 'build me an AI that replaces Google')",
                "3.2: Request is not a duplicate of a test submission or automated spam (no 'test123', 'asdfg', repeated characters)",
            ]
        },
    ]

    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.structured_llm = self.llm.with_structured_output(InputEvalResult)

        # Format dimensions into prompt text
        dimensions_text = ""
        for dim in self.DIMENSIONS:
            dimensions_text += f"\n### Dimension: {dim['name']} (threshold: {dim['threshold']}/{len(dim['criteria'])})\n"
            for criterion in dim["criteria"]:
                dimensions_text += f"- {criterion}\n"

        auto_fails_text = "\n".join(f"- {af}" for af in self.AUTO_FAIL_CONDITIONS)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Request Quality Gate for a web development agency's AI system.

Your job: Evaluate if a client's request is meaningful enough to spend engineering time on.
You use a Binary Criteria Framework — each check is YES (pass) or NO (fail). No partial credit.

---

## STEP 1: AUTO-FAIL CHECK

Check these conditions FIRST. If ANY is triggered, the request is immediately rejected:

{auto_fails}

---

## STEP 2: BINARY CRITERIA BY DIMENSION

Evaluate each criterion as YES (passed=true) or NO (passed=false).
For each criterion, you MUST provide:
- **evidence**: Cite the specific text from the request that supports your judgment
- **current_state**: What the request currently says/has for this criterion
- **required_fix**: If failed, what the client needs to provide. Empty string if passed.

{dimensions}

---

## STEP 3: FAILED CRITERIA FIXES

For every criterion that FAILED, output it in the failed_criteria_fixes list with:
- criterion_id (e.g. "1.1")
- criterion (the check name)
- current_state (what's there now)
- required_fix (specific fix the client should make)

---

## STEP 4: SCORING & VERDICT

**is_valid**: True ONLY if auto_fail_triggered is False AND all_dimensions_passed is True.
**score**: Calculate as (total criteria passed) / (total criteria). E.g. 5/6 = 0.83.
**category**: Classify as 'actionable', 'vague', 'off_topic', 'gibberish', 'duplicate_likely', or 'incomplete'.
**bar_raiser_decision**:
  - If PASS: "PASS — [1-sentence reason, citing strongest evidence]"
  - If FAIL: "FAIL — [which dimensions/auto-fails failed and what the client needs to fix]"

---

## STANDARDS

- Be binary: Each criterion is YES or NO. Not "partially." Not "sort of."
- Cite evidence: For each check, note what you saw (or didn't see) in the request.
- Be generous: Clients are not technical. Short or imperfect phrasing is fine as long as intent is clear.
- Be specific in fixes: Don't say "provide more detail" → say "Specify which page or section of the site this applies to."
- The bar for rejection is LOW: Only reject clearly meaningless, off-topic, or unactionable submissions.

Client ID: {client_id}
"""),
            ("user", "{request_text}")
        ])

        self.prompt = self.prompt.partial(
            auto_fails=auto_fails_text,
            dimensions=dimensions_text,
        )

        self.chain = self.prompt | self.structured_llm

    def evaluate(self, client_id: str, request_text: str) -> Dict[str, Any]:
        """
        Evaluate a raw client request before it enters the pipeline.

        Args:
            client_id: The client identifier (domain name)
            request_text: The raw text from the client's form submission

        Returns:
            Dict with full binary criteria evaluation results.
        """
        # Quick pre-checks before calling the LLM (matches AF1)
        if not request_text or not request_text.strip():
            return self._pre_check_rejection(
                reason="Request is empty.",
                category="gibberish",
                auto_fail="AF1: Request is empty, only whitespace, or fewer than 3 characters",
                suggested_clarification="Please describe what changes you'd like made to your website.",
            )

        stripped = request_text.strip()
        if len(stripped) < 3:
            return self._pre_check_rejection(
                reason="Request is too short to be meaningful.",
                category="gibberish",
                auto_fail="AF1: Request is empty, only whitespace, or fewer than 3 characters",
                suggested_clarification="Could you provide more detail about what you need?",
            )

        # LLM evaluation with binary criteria framework
        result: InputEvalResult = self.chain.invoke({
            "client_id": client_id,
            "request_text": stripped,
        })

        eval_dict = result.model_dump()

        # Enforce is_valid based on framework rules (LLM might be inconsistent)
        eval_dict["is_valid"] = (
            not eval_dict["auto_fail_triggered"]
            and eval_dict["all_dimensions_passed"]
        )

        eval_dict["model"] = self.llm.model
        eval_dict["usage"] = {}

        return eval_dict

    def _pre_check_rejection(
        self, reason: str, category: str, auto_fail: str, suggested_clarification: str
    ) -> Dict[str, Any]:
        """Build a rejection result for pre-LLM checks (empty/too-short)."""
        return {
            "auto_fail_checks": [
                {"condition": auto_fail, "triggered": True, "evidence": reason}
            ],
            "auto_fail_triggered": True,
            "dimension_results": [],
            "all_dimensions_passed": False,
            "failed_criteria_fixes": [],
            "is_valid": False,
            "score": 0.0,
            "category": category,
            "reason": reason,
            "issues": [reason],
            "suggested_clarification": suggested_clarification,
            "bar_raiser_decision": f"FAIL — Auto-fail triggered: {reason}",
            "model": "pre-check",
            "usage": {},
        }

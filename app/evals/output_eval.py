"""
Eval 2: Output Quality Evaluation (Binary Criteria Framework)
==============================================================
Runs AFTER the architect generates a plan, BEFORE pushing to ClickUp.

Framework (adapted from PRD Quality Gate course):
- Auto-fail conditions: Hard stops for dealbreaker outputs
- Binary criteria: Each check is YES/NO grouped into dimensions with thresholds
- Evidence per criterion: Cite what you found (or didn't find) in the plan
- "Current State" + "Required Fix" per failed criterion
- Rubric scoring: 0-5 per dimension (secondary signal, kept from v1)
- Critique + Self-Refinement: Detailed feedback with minimal-fix philosophy
- Delta reporting: Track v1 vs v2 improvements across iterations
- Bar Raiser decision: Final verdict with reasoning

The architect can use the critique + refinement instructions to improve on retry.
Only what FAILED gets fixed — passing content is preserved (minimal-fix philosophy).
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
    evidence: str = Field(description="What you saw (or didn't see) in the plan that triggered or passed this check")


# ---------------------------------------------------------------------------
# Binary criterion (YES/NO with evidence)
# ---------------------------------------------------------------------------

class BinaryCriterion(BaseModel):
    """A single binary criterion evaluation — pass or fail, with evidence."""
    criterion_id: str = Field(description="ID like '1.1', '1.2', '2.1' etc.")
    criterion: str = Field(description="What is being checked")
    passed: bool = Field(description="True if the criterion is met (YES), False if not (NO)")
    evidence: str = Field(description="Cite specific text from the plan that supports this judgment")
    current_state: str = Field(description="What the plan currently says/has for this criterion")
    required_fix: str = Field(description="What needs to change to pass. Empty string if passed.")


# ---------------------------------------------------------------------------
# Dimension result (group of criteria with threshold)
# ---------------------------------------------------------------------------

class DimensionResult(BaseModel):
    """Result for one evaluation dimension."""
    dimension_name: str = Field(description="Name of this dimension")
    criteria: List[BinaryCriterion] = Field(description="Individual criteria checks")
    passed_count: int = Field(description="Number of criteria that passed")
    total_count: int = Field(description="Total criteria in this dimension")
    threshold: int = Field(description="Minimum criteria needed to pass this dimension")
    dimension_passed: bool = Field(description="True if passed_count >= threshold")


# ---------------------------------------------------------------------------
# Rubric dimension scores (kept from v1 as secondary signal)
# ---------------------------------------------------------------------------

class RubricScore(BaseModel):
    """A single rubric dimension with a score and justification."""
    dimension: str = Field(description="Name of the rubric dimension being scored")
    score: int = Field(description="Score from 0 (terrible) to 5 (excellent)")
    justification: str = Field(description="One-sentence explanation for this score")


# ---------------------------------------------------------------------------
# Full evaluation result
# ---------------------------------------------------------------------------

class OutputEvalResult(BaseModel):
    """Complete structured evaluation of an architect-generated plan."""

    # Auto-fail checks
    auto_fail_checks: List[AutoFailCheck] = Field(
        description="Auto-fail condition checks — any trigger = immediate REJECT"
    )
    auto_fail_triggered: bool = Field(
        description="True if ANY auto-fail condition was triggered"
    )

    # Dimensional binary criteria (primary evaluation method)
    dimension_results: List[DimensionResult] = Field(
        description="Per-dimension evaluation results with binary criteria"
    )
    all_dimensions_passed: bool = Field(
        description="True only if ALL dimensions meet their threshold"
    )
    total_criteria_passed: int = Field(
        description="Total number of criteria that passed across all dimensions"
    )
    total_criteria: int = Field(
        description="Total number of criteria across all dimensions"
    )

    # Failed criteria with fixes (optimizer-style output)
    failed_criteria_fixes: List[Dict[str, str]] = Field(
        description="For each failed criterion: {'criterion_id', 'criterion', 'current_state', 'required_fix'}"
    )

    # Rubric scoring (secondary signal, kept from v1)
    rubric_scores: List[RubricScore] = Field(
        description="Scores for each evaluation dimension (0-5)"
    )
    rubric_total: float = Field(
        description="Average of all rubric scores (0.0 to 5.0)"
    )

    # Binary pass/fail legacy (kept for backward compatibility)
    binary_checks: List[Dict[str, Any]] = Field(
        description="Flattened list of all binary criteria as {check_name, passed, detail} for backward compat"
    )
    all_binary_passed: bool = Field(
        description="True only if ALL binary criteria passed across all dimensions"
    )

    # Critique (what's wrong)
    critique: str = Field(
        description="Detailed critique of the plan's weaknesses. 'No issues found.' if excellent."
    )

    # Self-refinement instructions (minimal-fix philosophy)
    refinement_instructions: str = Field(
        description="Specific, actionable fix instructions. Fix ONLY what failed. Preserve everything that passed. 'No refinement needed.' if the plan passes."
    )

    # Overall verdict
    verdict: str = Field(
        description="One of: 'APPROVE', 'REVISE', or 'REJECT'"
    )
    verdict_reason: str = Field(
        description="One-sentence summary of why this verdict was chosen"
    )

    # Bar Raiser decision
    bar_raiser_decision: str = Field(
        description="Final verdict: 'PASS — [reason]' or 'FAIL — [failed dimensions/auto-fails and what needs to change]'"
    )


class OutputEvaluator:
    """
    Evaluates the quality of an architect-generated technical plan using
    the Binary Criteria Framework with rubric scoring as a secondary signal.

    Uses:
    - Auto-fail conditions (hard stops)
    - 4 dimensions with binary criteria and thresholds
    - Evidence per criterion with "Current State" + "Required Fix"
    - Rubric scoring (0-5) as secondary signal
    - Critique + self-refinement with minimal-fix philosophy
    - Delta reporting across iterations
    - Bar Raiser decision

    Use this AFTER the architect node and BEFORE pushing to ClickUp.
    If verdict is 'REVISE', feed the formatted feedback back to the architect.
    """

    # Plan must score at least this rubric average to auto-approve
    RUBRIC_PASS_THRESHOLD = 3.5

    # --- Auto-Fail Conditions ---
    AUTO_FAIL_CONDITIONS = [
        "AF1: Plan has NO execution steps at all (the Execution Steps section is missing or empty)",
        "AF2: Plan addresses a DIFFERENT request than what the client actually asked for",
        "AF3: Plan hallucinate technologies or frameworks the client doesn't use (based on client context)",
    ]

    # --- Dimensions with Binary Criteria ---
    DIMENSIONS = [
        {
            "name": "Task & Context Clarity",
            "threshold": 3,
            "criteria": [
                "1.1: Plan has a Task Summary section with a concise 1-sentence goal",
                "1.2: Plan has a Technical Context section specifying environment, CMS/framework, and constraints",
                "1.3: Plan demonstrates understanding of the client's ACTUAL request (not a generic template)",
                "1.4: If client context was provided (tech stack, brand), the plan references it specifically",
            ]
        },
        {
            "name": "Execution Quality",
            "threshold": 4,
            "criteria": [
                "2.1: Execution steps are numbered and sequential (not a vague paragraph)",
                "2.2: Each step is specific enough that a developer could start working without guessing",
                "2.3: Steps reference specific files, components, pages, or system parts (not 'update the code')",
                "2.4: Steps are in a logical order (dependencies come before dependents)",
                "2.5: If the request involves UI changes, visual/layout details are specified",
            ]
        },
        {
            "name": "Completeness & Scope",
            "threshold": 4,
            "criteria": [
                "3.1: Every part of the client's request is addressed (nothing was ignored or skipped)",
                "3.2: Plan includes a Definition of Done checklist with items specific to THIS task",
                "3.3: Plan includes relevant tags for categorization",
                "3.4: If the request involves a new page or content, an SEO section is included",
                "3.5: Plan does NOT include work that wasn't requested (no scope creep)",
            ]
        },
        {
            "name": "Structural Integrity",
            "threshold": 3,
            "criteria": [
                "4.1: Plan follows the required Markdown structure (Summary, Context, Steps, Flow, Checklist)",
                "4.2: Plan includes an ASCII logic flow diagram where applicable",
                "4.3: Markdown renders correctly (proper headings, code blocks, lists)",
                "4.4: Plan uses only ASCII characters (no broken unicode or special characters)",
            ]
        },
    ]

    # --- Rubric Dimensions (secondary signal, kept from v1) ---
    RUBRIC_DIMENSIONS = [
        "Completeness — Does the plan address every part of the client's request?",
        "Clarity — Are the steps clear enough for a developer to follow without guessing?",
        "Technical Accuracy — Are the technical choices appropriate for the client's stack?",
        "Structure — Is the plan well-organized with proper sections (summary, steps, flow, checklist)?",
        "Actionability — Could a developer start working RIGHT NOW from this plan alone?",
    ]

    def __init__(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.structured_llm = self.llm.with_structured_output(OutputEvalResult)

        # Format dimensions into prompt text
        dimensions_text = ""
        for dim in self.DIMENSIONS:
            dimensions_text += f"\n### Dimension: {dim['name']} (threshold: {dim['threshold']}/{len(dim['criteria'])})\n"
            for criterion in dim["criteria"]:
                dimensions_text += f"- {criterion}\n"

        auto_fails_text = "\n".join(f"- {af}" for af in self.AUTO_FAIL_CONDITIONS)

        rubric_str = "\n".join(
            f"{i+1}. {dim}" for i, dim in enumerate(self.RUBRIC_DIMENSIONS)
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a Senior QA Evaluator for a web development agency's AI system.

You are reviewing a Technical Plan generated by an AI architect based on a client's request.
You use a Binary Criteria Framework — each check is YES (pass) or NO (fail). No partial credit.

---

## STEP 1: AUTO-FAIL CHECK

Check these conditions FIRST. If ANY is triggered, the plan is immediately REJECTED:

{auto_fails}

For each condition, provide evidence of what you found (or didn't find) in the plan.

---

## STEP 2: BINARY CRITERIA BY DIMENSION

Evaluate each criterion as YES (passed=true) or NO (passed=false).
For EACH criterion you MUST provide:
- **evidence**: Cite the specific text from the plan that supports your judgment
- **current_state**: What the plan currently says/has for this criterion
- **required_fix**: If failed, what specifically needs to change. Empty string if passed.

{dimensions}

Each dimension has a threshold. The dimension passes only if enough criteria pass.
Set all_dimensions_passed to True only if EVERY dimension meets its threshold.

---

## STEP 3: FAILED CRITERIA FIXES TABLE

For every criterion that FAILED, output it in the failed_criteria_fixes list with:
- criterion_id (e.g. "1.1")
- criterion (the check name)
- current_state (what's there now — be specific, quote the plan)
- required_fix (exact fix needed — be specific, not "improve this")

---

## STEP 4: RUBRIC SCORING (secondary signal)

Also score these dimensions on a 0-5 scale (this is a secondary signal, NOT used for the verdict):

{rubric_dimensions}

Scoring: 0=Missing/wrong, 1=Major problems, 2=Significant gaps, 3=Acceptable, 4=Good, 5=Excellent
Calculate rubric_total as the average.

---

## STEP 5: BACKWARD COMPATIBILITY

Also populate binary_checks as a flat list of ALL criteria across all dimensions, formatted as:
{{"check_name": "criterion text", "passed": true/false, "detail": "brief explanation"}}
Set all_binary_passed to True only if every single criterion passed.

---

## STEP 6: CRITIQUE & SELF-REFINEMENT (Minimal-Fix Philosophy)

**Critique**: Write a detailed paragraph about what's wrong with the plan.
Focus on gaps, inaccuracies, unclear steps, or missing information.
If the plan is genuinely good, write "No issues found."

**Refinement Instructions**: Write specific, actionable fix instructions.

CRITICAL — MINIMAL-FIX PHILOSOPHY:
- Fix ONLY what failed. Do NOT rewrite sections that already passed.
- Add the MINIMUM content needed to flip each failed criterion from NO to YES.
- Do NOT add new features, expand scope, or over-engineer.
- Reference the specific criterion ID and section that needs fixing.
- Example GOOD fix: "Criterion 2.3 failed — Step 3 says 'update the database' but doesn't specify which tables. Add: 'Modify the `users` table to add a `refund_status` column.'"
- Example BAD fix: "Rewrite all execution steps to be more comprehensive."

If no refinement is needed, write "No refinement needed."

---

## STEP 7: VERDICT & BAR RAISER

**Verdict logic:**
- **APPROVE**: auto_fail_triggered is False AND all_dimensions_passed is True
- **REVISE**: auto_fail_triggered is False AND some dimensions failed — plan has potential but needs fixes
- **REJECT**: auto_fail_triggered is True — plan is fundamentally off

**bar_raiser_decision:**
- If PASS: "PASS — All {total_dim} dimensions meet thresholds. [cite strongest evidence]"
- If FAIL: "FAIL — [X] dimension(s) failed: [names]. Required fixes: [list top 3 fixes]"

---

## STANDARDS

- Be binary: Each criterion is YES or NO. Not "partially." Not "sort of."
- Cite evidence: For each check, quote or reference specific text from the plan.
- Be fair: If a criterion is met, mark it YES — don't add extra requirements mid-evaluation.
- Be specific in fixes: Don't say "improve steps" → say "Step 3 needs to specify which API endpoint to call."
- Focus on failed criteria: The optimizer/architect only needs to fix what failed.

Client Context (for reference):
{client_context}
"""),
            ("user", """## Original Client Request:
{request}

## Generated Technical Plan:
{plan}

Evaluate this plan now.""")
        ])

        total_criteria = sum(len(d["criteria"]) for d in self.DIMENSIONS)
        total_dim = len(self.DIMENSIONS)

        self.prompt = self.prompt.partial(
            auto_fails=auto_fails_text,
            dimensions=dimensions_text,
            rubric_dimensions=rubric_str,
            total_dim=str(total_dim),
        )

        self.chain = self.prompt | self.structured_llm

    def evaluate(
        self,
        request: str,
        plan_markdown: str,
        client_context: dict = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a generated technical plan.

        Args:
            request: The original client request text
            plan_markdown: The architect's generated plan (markdown)
            client_context: Optional dict of client info (tech stack, brand, etc.)

        Returns:
            Dict with full binary criteria evaluation + rubric scoring results.
        """
        context_str = str(client_context) if client_context else "No additional context available."

        result: OutputEvalResult = self.chain.invoke({
            "request": request,
            "plan": plan_markdown,
            "client_context": context_str,
        })

        eval_dict = result.model_dump()

        # Enforce verdict based on framework rules (LLM might be inconsistent)
        if eval_dict["auto_fail_triggered"]:
            eval_dict["verdict"] = "REJECT"
        elif not eval_dict["all_dimensions_passed"]:
            eval_dict["verdict"] = "REVISE"
        else:
            eval_dict["verdict"] = "APPROVE"

        eval_dict["model"] = self.llm.model
        eval_dict["usage"] = {}

        return eval_dict

    def format_feedback_for_architect(self, eval_result: Dict[str, Any]) -> str:
        """
        Format the evaluation result into feedback for the architect's retry loop.

        Uses the MINIMAL-FIX PHILOSOPHY from the course:
        - Fix ONLY what failed (criteria marked NO)
        - Preserve ALL passing content (criteria marked YES)
        - No scope creep — add minimum content needed
        - Mark changes with specific criterion IDs

        Args:
            eval_result: The dict returned by evaluate()

        Returns:
            A formatted string to inject into the architect's next prompt.
        """
        lines = []
        lines.append("## QA EVALUATION FEEDBACK")
        lines.append("")
        lines.append("CRITICAL INSTRUCTIONS: Fix ONLY what failed. Do NOT rewrite sections that already passed.")
        lines.append("Add the MINIMUM content needed to flip each failed criterion. No scope creep.")
        lines.append("")

        # Verdict + Bar Raiser
        lines.append(f"**Verdict: {eval_result['verdict']}** — {eval_result['verdict_reason']}")
        lines.append(f"**Bar Raiser: {eval_result['bar_raiser_decision']}**")
        lines.append("")

        # Auto-fail status
        if eval_result["auto_fail_triggered"]:
            lines.append("**AUTO-FAIL TRIGGERED:**")
            for af in eval_result["auto_fail_checks"]:
                if af["triggered"]:
                    lines.append(f"- {af['condition']}: {af['evidence']}")
            lines.append("")

        # Dimension results summary
        lines.append("**DIMENSION RESULTS:**")
        lines.append("| Dimension | Passed | Total | Threshold | Result |")
        lines.append("|-----------|--------|-------|-----------|--------|")
        for dim in eval_result["dimension_results"]:
            result_str = "PASS" if dim["dimension_passed"] else "FAIL"
            lines.append(f"| {dim['dimension_name']} | {dim['passed_count']} | {dim['total_count']} | {dim['threshold']} | {result_str} |")
        lines.append("")

        # Failed criteria fixes table (the key part — tells architect exactly what to fix)
        failed = eval_result.get("failed_criteria_fixes", [])
        if failed:
            lines.append(f"**FAILED CRITERIA — FIX THESE {len(failed)} ITEMS:**")
            lines.append("| # | Criterion | Current State | Required Fix |")
            lines.append("|---|-----------|---------------|--------------|")
            for fix in failed:
                lines.append(f"| {fix.get('criterion_id', '?')} | {fix.get('criterion', '?')} | {fix.get('current_state', '?')} | {fix.get('required_fix', '?')} |")
            lines.append("")

        # Rubric scores (secondary signal)
        lines.append(f"**Rubric Score: {eval_result['rubric_total']:.1f} / 5.0**")
        for score in eval_result["rubric_scores"]:
            indicator = "PASS" if score["score"] >= 4 else "NEEDS WORK" if score["score"] >= 2 else "FAIL"
            lines.append(f"- [{indicator}] {score['dimension']}: {score['score']}/5 — {score['justification']}")
        lines.append("")

        # Critique
        if eval_result["critique"] != "No issues found.":
            lines.append(f"**Critique:** {eval_result['critique']}")
            lines.append("")

        # Refinement instructions
        if eval_result["refinement_instructions"] != "No refinement needed.":
            lines.append(f"**Fix Instructions:** {eval_result['refinement_instructions']}")
            lines.append("")

        # Reminder
        lines.append("---")
        lines.append("REMEMBER: Fix ONLY the failed criteria above. Preserve everything that passed. No scope creep.")

        return "\n".join(lines)

    def format_delta_report(
        self, prev_eval: Dict[str, Any], curr_eval: Dict[str, Any], iteration: int
    ) -> str:
        """
        Generate a delta report comparing previous evaluation to current evaluation.
        Shows which criteria flipped from FAIL to PASS (like the re-evaluator in the course).

        Args:
            prev_eval: Previous iteration's eval result dict
            curr_eval: Current iteration's eval result dict
            iteration: Current iteration number (1-indexed)

        Returns:
            Formatted delta report string.
        """
        lines = []
        lines.append(f"## Delta Report: v{iteration-1} → v{iteration}")
        lines.append("")

        prev_total = prev_eval.get("total_criteria_passed", 0)
        curr_total = curr_eval.get("total_criteria_passed", 0)
        total = curr_eval.get("total_criteria", 0)

        lines.append(f"**Total Criteria Passed:** v{iteration-1}: {prev_total}/{total} → v{iteration}: {curr_total}/{total}")
        if curr_total > prev_total:
            lines.append(f"**Improvement: +{curr_total - prev_total} criteria fixed**")
        elif curr_total == prev_total:
            lines.append("**No improvement — same criteria pass count**")
        lines.append("")

        # Build lookup of previous criteria results
        prev_criteria = {}
        for dim in prev_eval.get("dimension_results", []):
            for c in dim.get("criteria", []):
                prev_criteria[c["criterion_id"]] = c["passed"]

        # Find flips
        flipped = []
        for dim in curr_eval.get("dimension_results", []):
            for c in dim.get("criteria", []):
                cid = c["criterion_id"]
                was_pass = prev_criteria.get(cid)
                now_pass = c["passed"]
                if was_pass is False and now_pass is True:
                    flipped.append({"id": cid, "criterion": c["criterion"], "fix_applied": c["current_state"]})

        if flipped:
            lines.append("**Criteria Flipped FAIL → PASS:**")
            lines.append("| # | Criterion | What Was Fixed |")
            lines.append("|---|-----------|----------------|")
            for f in flipped:
                lines.append(f"| {f['id']} | {f['criterion']} | {f['fix_applied']} |")
            lines.append("")

        # Dimension comparison
        lines.append("**Dimension Comparison:**")
        lines.append(f"| Dimension | v{iteration-1} | v{iteration} | Delta |")
        lines.append("|-----------|------|------|-------|")

        prev_dims = {d["dimension_name"]: d for d in prev_eval.get("dimension_results", [])}
        for dim in curr_eval.get("dimension_results", []):
            name = dim["dimension_name"]
            prev_dim = prev_dims.get(name, {})
            prev_res = "PASS" if prev_dim.get("dimension_passed") else "FAIL"
            curr_res = "PASS" if dim["dimension_passed"] else "FAIL"
            delta = "→" if prev_res == curr_res else f"{prev_res}→{curr_res}"
            lines.append(f"| {name} | {prev_res} | {curr_res} | {delta} |")
        lines.append("")

        # Overall
        prev_verdict = prev_eval.get("verdict", "?")
        curr_verdict = curr_eval.get("verdict", "?")
        lines.append(f"**v{iteration-1} Verdict:** {prev_verdict}")
        lines.append(f"**v{iteration} Verdict:** {curr_verdict}")

        return "\n".join(lines)

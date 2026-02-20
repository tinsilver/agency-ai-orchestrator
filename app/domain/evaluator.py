import re
from typing import Dict, Optional
from langfuse import get_client

# Claude Haiku 4.5 pricing (USD per token)
PRICING = {
    "claude-haiku-4-5-20251001": {"input": 1.00 / 1_000_000, "output": 5.00 / 1_000_000},
}


class LightweightValidator:
    """Quick sanity checks that run on every request. Reports scores to Langfuse."""

    def __init__(self):
        self.langfuse = get_client()

    def validate(self, request_text: str, plan: Optional[str] = None) -> Dict[str, float]:
        """Run non-LLM checks and report scores to the current Langfuse trace."""
        scores = {}

        # 1. Length check
        request_length = len(request_text.strip())
        scores["request_length_ok"] = 1.0 if request_length >= 10 else 0.0

        # 2. Empty check
        scores["not_empty"] = 1.0 if request_length > 0 else 0.0

        # 3. Has action verb
        action_verbs = r'\b(add|change|fix|update|create|remove|build|improve|migrate|redesign)\b'
        scores["has_action_verb"] = 1.0 if re.search(action_verbs, request_text, re.IGNORECASE) else 0.0

        # 4. Auto-fail greeting check
        is_greeting_only = bool(re.match(r'^(hi|hello|thanks|ok|sure)[\s.,!?]*$', request_text.strip(), re.IGNORECASE))
        scores["auto_fail_greeting"] = 0.0 if is_greeting_only else 1.0

        # 5. Plan structure check
        if plan:
            has_execution = "## Execution Steps" in plan or "## 📋 Execution Steps" in plan
            has_summary = "## Task Summary" in plan or "## 📝 Task Summary" in plan
            scores["plan_has_structure"] = 1.0 if (has_execution and has_summary) else 0.0

        # Send scores to current Langfuse trace
        for name, value in scores.items():
            self.langfuse.score_current_trace(
                name=name,
                value=value,
                data_type="BOOLEAN",
            )

        return scores

    def report_usage(self, usage: dict, model: str) -> Dict[str, float]:
        """Send token usage and cost as NUMERIC scores to the current Langfuse trace."""
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens

        rates = PRICING.get(model, PRICING["claude-haiku-4-5-20251001"])
        cost_usd = (input_tokens * rates["input"]) + (output_tokens * rates["output"])

        scores = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost_usd, 6),
        }

        for name, value in scores.items():
            self.langfuse.score_current_trace(
                name=name,
                value=value,
                data_type="NUMERIC",
            )

        return scores

    def report_enrichment_metrics(self, state: Dict) -> Dict[str, float]:
        """
        Report enrichment-specific metrics to Langfuse trace.

        Args:
            state: AgentState dict containing enrichment tracking fields

        Returns:
            Dict of metric names to values
        """
        enrichment_history = state.get("enrichment_history", [])
        tool_usage_stats = state.get("tool_usage_stats", {})
        missing_information = state.get("missing_information", [])

        metrics = {}

        # Enrichment performance metrics
        metrics["enrichment_iterations"] = len(enrichment_history)
        metrics["enrichment_success"] = 1.0 if state.get("enrichment_complete") else 0.0
        metrics["enrichment_total_tokens"] = state.get("total_enrichment_tokens", 0)

        # Calculate total enrichment cost
        total_cost = 0.0
        for iteration in enrichment_history:
            tokens = iteration.get("tokens_used", 0)
            rates = PRICING["claude-haiku-4-5-20251001"]
            # Assume 50/50 split of input/output for estimation
            total_cost += (tokens * 0.5 * rates["input"]) + (tokens * 0.5 * rates["output"])
        metrics["enrichment_cost_usd"] = round(total_cost, 6)

        # Information quality metrics
        questions_initially_missing = len(missing_information) if missing_information else 0
        questions_answered = 0
        for iteration in enrichment_history:
            questions_answered += iteration.get("questions_resolved", 0)

        metrics["questions_initially_missing"] = questions_initially_missing
        metrics["questions_answered_by_enrichment"] = questions_answered

        if questions_initially_missing > 0:
            metrics["enrichment_answer_rate"] = round(questions_answered / questions_initially_missing, 2)
        else:
            metrics["enrichment_answer_rate"] = 0.0

        # Final confidence score
        if enrichment_history:
            last_iteration = enrichment_history[-1]
            metrics["final_enrichment_confidence"] = last_iteration.get("confidence", 0.0)

        # Tool usage metrics
        for tool_name, stats in tool_usage_stats.items():
            metrics[f"tool_{tool_name}_calls"] = stats.get("calls", 0)

        # Report all metrics to Langfuse
        # Numeric metrics
        numeric_metrics = [
            "enrichment_iterations",
            "enrichment_total_tokens",
            "enrichment_cost_usd",
            "questions_initially_missing",
            "questions_answered_by_enrichment",
            "enrichment_answer_rate",
            "final_enrichment_confidence",
        ]
        for name in numeric_metrics:
            if name in metrics:
                self.langfuse.score_current_trace(
                    name=name,
                    value=metrics[name],
                    data_type="NUMERIC",
                )

        # Tool usage metrics
        for name, value in metrics.items():
            if name.startswith("tool_") and name.endswith("_calls"):
                self.langfuse.score_current_trace(
                    name=name,
                    value=value,
                    data_type="NUMERIC",
                )

        # Boolean metrics
        self.langfuse.score_current_trace(
            name="enrichment_success",
            value=metrics["enrichment_success"],
            data_type="BOOLEAN",
        )

        # Categorical metric: stop reason
        if state.get("enrichment_stop_reason"):
            self.langfuse.score_current_trace(
                name="enrichment_stop_reason",
                value=state["enrichment_stop_reason"],
                data_type="CATEGORICAL",
            )

        return metrics

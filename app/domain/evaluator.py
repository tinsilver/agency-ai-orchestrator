import re
from typing import Dict, Optional
from langfuse import get_client


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

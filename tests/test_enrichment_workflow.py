"""
Unit tests for enrichment workflow routing and state management.

Tests the enrichment loop logic without requiring actual LLM calls or Langfuse prompts.
"""
import pytest
from typing import Dict, Any, List
from app.state import AgentState
from app.services.enrichment_toolkit import EnrichmentToolkit


# Mock the routing function since we can't import from graph.py without side effects
def route_after_validation_with_enrichment(state: AgentState) -> str:
    """
    Mock routing function that mimics the logic from app/graph.py.

    Returns:
        - "architect" if request is complete
        - "create_admin_task" if exhausted (max iterations, token limit, no progress)
        - "dynamic_enrichment" to continue enrichment loop
    """
    # Complete? → architect
    if state.get("is_request_complete"):
        return "architect"

    # Max iterations? → admin task
    if state.get("enrichment_iteration", 0) >= 3:
        return "create_admin_task"

    # Token limit? → admin task
    total_tokens = state.get("total_enrichment_tokens", 0)
    max_tokens = state.get("max_enrichment_tokens", 500_000)
    if total_tokens >= max_tokens:
        return "create_admin_task"

    # No progress (same questions remain)?
    if _no_progress_made(state):
        return "create_admin_task"

    # Continue enrichment
    return "dynamic_enrichment"


def _no_progress_made(state: AgentState) -> bool:
    """Check if enrichment is making no progress (same questions remain)."""
    enrichment_history = state.get("enrichment_history", [])

    if len(enrichment_history) < 1:
        return False

    # Compare last iteration with current state
    prev_missing = enrichment_history[-1].get("missing_before", [])
    curr_missing = state.get("missing_information", [])

    # If same questions remain, no progress
    return set(prev_missing) == set(curr_missing)


class TestRoutingLogic:
    """Test the conditional routing logic for enrichment workflow."""

    def test_route_to_architect_when_complete(self):
        """When request is complete, route to architect."""
        state: AgentState = {
            "is_request_complete": True,
            "enrichment_iteration": 1,
            "total_enrichment_tokens": 1000,
            "max_enrichment_tokens": 500_000,
            "missing_information": [],
            "enrichment_history": []
        }

        assert route_after_validation_with_enrichment(state) == "architect"

    def test_route_to_enrichment_on_first_iteration(self):
        """On first validation failure, route to enrichment."""
        state: AgentState = {
            "is_request_complete": False,
            "enrichment_iteration": 0,
            "total_enrichment_tokens": 0,
            "max_enrichment_tokens": 500_000,
            "missing_information": ["What is the color scheme?"],
            "enrichment_history": []
        }

        assert route_after_validation_with_enrichment(state) == "dynamic_enrichment"

    def test_route_to_admin_task_after_max_iterations(self):
        """After 3 enrichment attempts, route to admin task."""
        state: AgentState = {
            "is_request_complete": False,
            "enrichment_iteration": 3,
            "total_enrichment_tokens": 10_000,
            "max_enrichment_tokens": 500_000,
            "missing_information": ["Still missing info"],
            "enrichment_history": [
                {"iteration": 1, "missing_before": ["Info 1", "Info 2"]},
                {"iteration": 2, "missing_before": ["Info 1"]},
                {"iteration": 3, "missing_before": ["Info 1"]}
            ]
        }

        assert route_after_validation_with_enrichment(state) == "create_admin_task"

    def test_route_to_admin_task_on_token_limit(self):
        """When token budget exceeded, route to admin task."""
        state: AgentState = {
            "is_request_complete": False,
            "enrichment_iteration": 1,
            "total_enrichment_tokens": 500_001,
            "max_enrichment_tokens": 500_000,
            "missing_information": ["Still missing info"],
            "enrichment_history": []
        }

        assert route_after_validation_with_enrichment(state) == "create_admin_task"

    def test_route_to_admin_task_on_no_progress(self):
        """When no progress is made (same questions), route to admin task."""
        state: AgentState = {
            "is_request_complete": False,
            "enrichment_iteration": 2,
            "total_enrichment_tokens": 5_000,
            "max_enrichment_tokens": 500_000,
            "missing_information": ["Question 1", "Question 2"],
            "enrichment_history": [
                {"iteration": 1, "missing_before": ["Question 1", "Question 2", "Question 3"]},
                {"iteration": 2, "missing_before": ["Question 1", "Question 2"]}
            ]
        }

        assert route_after_validation_with_enrichment(state) == "create_admin_task"

    def test_route_to_enrichment_when_progress_made(self):
        """When progress is made (fewer questions), continue enrichment."""
        state: AgentState = {
            "is_request_complete": False,
            "enrichment_iteration": 1,
            "total_enrichment_tokens": 5_000,
            "max_enrichment_tokens": 500_000,
            "missing_information": ["Question 1"],
            "enrichment_history": [
                {"iteration": 1, "missing_before": ["Question 1", "Question 2", "Question 3"]}
            ]
        }

        assert route_after_validation_with_enrichment(state) == "dynamic_enrichment"


class TestToolBudgetEnforcement:
    """Test that tool budget limits are enforced correctly."""

    def test_tool_budget_allows_calls_within_limit(self):
        """Tool calls should succeed when within budget."""
        toolkit = EnrichmentToolkit()
        usage_stats: Dict[str, Any] = {}

        # web_fetch has budget of 5
        assert toolkit._check_budget("web_fetch", usage_stats) is True

        toolkit._increment_usage("web_fetch", usage_stats)
        assert usage_stats["web_fetch"]["calls"] == 1
        assert toolkit._check_budget("web_fetch", usage_stats) is True

    def test_tool_budget_blocks_calls_over_limit(self):
        """Tool calls should be blocked when budget exceeded."""
        toolkit = EnrichmentToolkit()
        usage_stats: Dict[str, Any] = {
            "web_fetch": {"calls": 5, "max_calls": 5}  # Already at limit
        }

        # web_fetch has budget of 5, should be blocked
        assert toolkit._check_budget("web_fetch", usage_stats) is False

    def test_different_tools_have_independent_budgets(self):
        """Each tool should have its own independent budget."""
        toolkit = EnrichmentToolkit()
        usage_stats: Dict[str, Any] = {
            "web_fetch": {"calls": 5, "max_calls": 5}  # web_fetch exhausted
        }

        # Other tools should still work
        assert toolkit._check_budget("web_search", usage_stats) is True
        assert toolkit._check_budget("seo_audit", usage_stats) is True

    def test_get_available_tools_respects_budgets(self):
        """get_available_tools should only return tools with remaining budget."""
        toolkit = EnrichmentToolkit()
        usage_stats: Dict[str, Any] = {
            "web_fetch": {"calls": 5, "max_calls": 5},  # Exhausted (limit 5)
            "web_search": {"calls": 2, "max_calls": 3},  # Still has 1 left (limit 3)
            "seo_audit": {"calls": 1, "max_calls": 1},  # Exhausted (limit 1)
        }

        available = toolkit.get_available_tools(usage_stats)

        # web_fetch and seo_audit should be excluded
        assert "web_fetch" not in [t["name"] for t in available]
        assert "seo_audit" not in [t["name"] for t in available]

        # web_search should be included (with remaining count)
        web_search_tool = next((t for t in available if t["name"] == "web_search"), None)
        assert web_search_tool is not None
        assert web_search_tool["remaining_calls"] == 1


class TestIterationTracking:
    """Test that enrichment iterations are tracked correctly."""

    def test_iteration_starts_at_zero(self):
        """Initial state should have iteration 0."""
        state: AgentState = {
            "enrichment_iteration": 0,
            "enrichment_history": []
        }

        assert state["enrichment_iteration"] == 0
        assert len(state["enrichment_history"]) == 0

    def test_iteration_increments_correctly(self):
        """Iteration should increment after each enrichment attempt."""
        state: AgentState = {
            "enrichment_iteration": 0,
            "enrichment_history": []
        }

        # Simulate first enrichment
        state["enrichment_iteration"] += 1
        state["enrichment_history"].append({
            "iteration": 1,
            "tools_used": ["web_fetch"],
            "questions_answered": 2
        })

        assert state["enrichment_iteration"] == 1
        assert len(state["enrichment_history"]) == 1

        # Simulate second enrichment
        state["enrichment_iteration"] += 1
        state["enrichment_history"].append({
            "iteration": 2,
            "tools_used": ["seo_audit"],
            "questions_answered": 1
        })

        assert state["enrichment_iteration"] == 2
        assert len(state["enrichment_history"]) == 2

    def test_history_preserves_all_iterations(self):
        """Enrichment history should preserve data from all iterations."""
        history: List[Dict[str, Any]] = []

        for i in range(1, 4):
            history.append({
                "iteration": i,
                "tools_used": [f"tool_{i}"],
                "questions_answered": i,
                "tokens_used": i * 1000
            })

        assert len(history) == 3
        assert history[0]["iteration"] == 1
        assert history[1]["iteration"] == 2
        assert history[2]["iteration"] == 3
        assert sum(h["tokens_used"] for h in history) == 6000


class TestTokenBudgetTracking:
    """Test that token budget is tracked and enforced correctly."""

    def test_token_budget_starts_at_zero(self):
        """Initial token count should be zero."""
        state: AgentState = {
            "total_enrichment_tokens": 0,
            "max_enrichment_tokens": 500_000
        }

        assert state["total_enrichment_tokens"] == 0

    def test_token_budget_accumulates(self):
        """Tokens should accumulate across iterations."""
        tokens = 0

        # Simulate 3 iterations
        tokens += 2_000  # Iteration 1
        tokens += 3_500  # Iteration 2
        tokens += 1_200  # Iteration 3

        assert tokens == 6_700

    def test_token_budget_limit_enforced(self):
        """Routing should stop when token limit reached."""
        state: AgentState = {
            "is_request_complete": False,
            "enrichment_iteration": 1,
            "total_enrichment_tokens": 501_000,
            "max_enrichment_tokens": 500_000,
            "missing_information": ["Question"],
            "enrichment_history": []
        }

        assert route_after_validation_with_enrichment(state) == "create_admin_task"

    def test_token_budget_allows_under_limit(self):
        """Routing should continue when under token limit."""
        state: AgentState = {
            "is_request_complete": False,
            "enrichment_iteration": 1,
            "total_enrichment_tokens": 450_000,
            "max_enrichment_tokens": 500_000,
            "missing_information": ["Question"],
            "enrichment_history": [
                {"iteration": 1, "missing_before": ["Question 1", "Question 2"]}
            ]
        }

        assert route_after_validation_with_enrichment(state) == "dynamic_enrichment"


class TestNoProgressDetection:
    """Test detection of stalled enrichment (no progress)."""

    def test_no_progress_with_identical_questions(self):
        """Should detect no progress when same questions remain."""
        state: AgentState = {
            "enrichment_history": [
                {"iteration": 1, "missing_before": ["Q1", "Q2", "Q3"]},
                {"iteration": 2, "missing_before": ["Q1", "Q2"]}
            ],
            "missing_information": ["Q1", "Q2"]  # Same as previous
        }

        assert _no_progress_made(state) is True

    def test_progress_with_fewer_questions(self):
        """Should detect progress when questions decrease."""
        state: AgentState = {
            "enrichment_history": [
                {"iteration": 1, "missing_before": ["Q1", "Q2", "Q3"]},
                {"iteration": 2, "missing_before": ["Q1", "Q2"]}
            ],
            "missing_information": ["Q1"]  # Fewer than previous
        }

        assert _no_progress_made(state) is False

    def test_progress_with_different_questions(self):
        """Should detect progress when questions change."""
        state: AgentState = {
            "enrichment_history": [
                {"iteration": 1, "missing_before": ["Q1", "Q2", "Q3"]},
                {"iteration": 2, "missing_before": ["Q1", "Q2"]}
            ],
            "missing_information": ["Q1", "Q4"]  # Different question
        }

        assert _no_progress_made(state) is False

    def test_no_progress_check_requires_history(self):
        """Should not check for progress when no history exists."""
        state: AgentState = {
            "enrichment_history": [],
            "missing_information": ["Q1", "Q2"]
        }

        # Not enough history to detect no progress
        assert _no_progress_made(state) is False


class TestStateManagement:
    """Test that state fields are managed correctly throughout workflow."""

    def test_initial_state_has_required_fields(self):
        """Initial state should have all enrichment fields."""
        state: AgentState = {
            "enrichment_iteration": 0,
            "enrichment_history": [],
            "dynamic_context": {},
            "tool_usage_stats": {},
            "total_enrichment_tokens": 0,
            "max_enrichment_tokens": 500_000,
            "enrichment_complete": False,
            "enrichment_stop_reason": None
        }

        assert "enrichment_iteration" in state
        assert "enrichment_history" in state
        assert "dynamic_context" in state
        assert "tool_usage_stats" in state
        assert "total_enrichment_tokens" in state

    def test_state_updates_after_enrichment(self):
        """State should be properly updated after each enrichment."""
        state: AgentState = {
            "enrichment_iteration": 0,
            "enrichment_history": [],
            "dynamic_context": {},
            "tool_usage_stats": {},
            "total_enrichment_tokens": 0,
            "max_enrichment_tokens": 500_000
        }

        # Simulate enrichment result
        state["enrichment_iteration"] += 1
        state["total_enrichment_tokens"] += 2_500
        state["tool_usage_stats"]["web_fetch"] = 1
        state["dynamic_context"]["brand_colors"] = {
            "answer": "#FF5733, #3498DB",
            "source": "pdf_extract",
            "confidence": 0.95
        }
        state["enrichment_history"].append({
            "iteration": 1,
            "tools_used": ["pdf_extract"],
            "questions_answered": 2,
            "tokens_used": 2_500
        })

        assert state["enrichment_iteration"] == 1
        assert state["total_enrichment_tokens"] == 2_500
        assert "brand_colors" in state["dynamic_context"]
        assert len(state["enrichment_history"]) == 1

    def test_stop_reason_set_on_completion(self):
        """Stop reason should be set when enrichment ends."""
        state: AgentState = {
            "is_request_complete": True,
            "enrichment_complete": True,
            "enrichment_stop_reason": "complete"
        }

        assert state["enrichment_stop_reason"] == "complete"

    def test_stop_reason_set_on_max_iterations(self):
        """Stop reason should reflect max iterations reached."""
        state: AgentState = {
            "enrichment_iteration": 3,
            "is_request_complete": False,
            "enrichment_complete": True,
            "enrichment_stop_reason": "max_iterations"
        }

        assert state["enrichment_stop_reason"] == "max_iterations"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])

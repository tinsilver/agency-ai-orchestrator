import pytest
from unittest.mock import Mock, patch
from dotenv import load_dotenv
load_dotenv()

from app.agents.review import ReviewAgent

class TestReviewAgent:
    def test_review_plan_approval(self):
        """Test that a good plan gets approved"""
        agent = ReviewAgent()
        
        request = "Create a contact form"
        plan = """
        ## Task Summary
        Build a contact form with validation
        
        ## Execution Steps
        1. Create form component
        2. Add validation
        3. Test submission
        """
        
        result = agent.review_plan(request=request, plan=plan)
        
        assert "content" in result
        assert "model" in result
        assert "usage" in result
    
    def test_review_plan_rejection(self):
        """Test that an incomplete plan gets critique"""
        agent = ReviewAgent()
        
        request = "Create a contact form with email validation"
        plan = "Build a form"  # Too vague
        
        result = agent.review_plan(request=request, plan=plan)
        
        # Should contain critique, not just "APPROVE"
        assert result["content"] != "APPROVE"
        assert len(result["content"]) > 20
    
    @patch('langfuse.Langfuse.get_prompt')
    def test_prompt_fetching(self, mock_get_prompt):
        """Test that prompt is fetched correctly from Langfuse"""
        mock_prompt = Mock()
        mock_prompt.compile.return_value = [
            {"role": "system", "content": "You are a QA Lead..."},
            {"role": "user", "content": "Plan to review"}
        ]
        mock_get_prompt.return_value = mock_prompt
        
        agent = ReviewAgent()
        agent.review_plan("test request", "test plan")
        
        mock_get_prompt.assert_called_once_with("qa-review-agent", label="production")
        mock_prompt.compile.assert_called_once()
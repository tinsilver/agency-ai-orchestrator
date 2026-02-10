Feature: Enhance the validation of the request with categorization, evaluation for completeness and potential routing to admin task creation

Context: We are a web design and hosting agency. Our clients submit requests through a form on our website. We want to use AI to validate and categorize these requests before they are assigned to a human agent. 

Plan:

1. Updated AgentState

```python
from typing import TypedDict, Literal, Annotated, Optional
import operator

class AgentState(TypedDict):
    # Input
    request: str
    client_context: dict
    file_summaries: list
    website_content: str
    
    # Request Classification & Validation
    request_category: str  # e.g., "blog_post", "seo_optimization", "bug_fix", etc.
    request_subcategories: list[str]  # Can have multiple classifications
    is_request_complete: bool
    missing_information: list[str]  # Specific items that are missing
    
    # Architect output
    plan: dict
    
    # QA state
    qa_attempts: Annotated[int, operator.add]
    qa_feedback: str
    qa_approved: bool
    
    # Task management
    needs_admin_review: bool
    admin_task_id: Optional[str]
    clickup_task_id: Optional[str]
    needs_escalation: bool

# Category constants for type safety
class RequestCategory:
    """Domain model for request classifications"""
    BLOG_POST = "blog_post"
    SEO_OPTIMIZATION = "seo_optimization"
    BUG_FIX = "bug_fix"
    CONTENT_UPDATE = "content_update"
    BUSINESS_INFO_UPDATE = "business_info_update"
    NEW_PAGE = "new_page"
    FORM_CHANGES = "form_changes"
    DESIGN_CHANGES = "design_changes"
    FEATURE_REQUEST = "feature_request"
    UNCLEAR = "unclear"
```

2. Enhanced Validate Request Node

```python
from langfuse import Langfuse, observe
from langchain_anthropic import ChatAnthropic
import json
from typing import Dict, Any

class RequestValidator:
    """Domain service for request classification and validation"""
    
    def __init__(self):
        self.langfuse = Langfuse()
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
    
    @observe(name="validate-and-classify-request")
    def validate_and_classify(
        self, 
        request: str, 
        client_context: dict,
        file_summaries: list = None,
        website_content: str = None
    ) -> Dict[str, Any]:
        """
        Classify request and validate completeness.
        Returns classification, completeness, and missing info.
        """
        # Fetch validation prompt from Langfuse
        prompt = self.langfuse.get_prompt("request-validator-classifier", label="production")
        
        # Format context
        file_context = self._format_file_context(file_summaries)
        website_ctx = website_content if website_content else "No website context available"
        
        compiled = prompt.compile(
            request=request,
            client_context=str(client_context),
            file_context=file_context,
            website_context=website_ctx
        )
        
        # Convert to LangChain messages
        messages = [(msg["role"], msg["content"]) for msg in compiled]
        
        response = self.llm.invoke(messages)
        
        # Parse structured JSON response
        try:
            result = json.loads(response.content)
            return {
                "request_category": result.get("primary_category", RequestCategory.UNCLEAR),
                "request_subcategories": result.get("subcategories", []),
                "is_request_complete": result.get("complete", False),
                "missing_information": result.get("missing", [])
            }
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "request_category": RequestCategory.UNCLEAR,
                "request_subcategories": [],
                "is_request_complete": False,
                "missing_information": ["Could not parse request - needs manual review"]
            }
    
    def _format_file_context(self, file_summaries: list = None) -> str:
        if not file_summaries:
            return "No files attached"
        
        context = "Attached files:\n"
        for file in file_summaries:
            if file.get("error"):
                context += f"- {file.get('filename', 'unknown')}: Error\n"
            else:
                context += f"- {file.get('filename', 'unknown')} ({file.get('type', 'unknown')})\n"
        return context

# Node function for the graph
def validate_request(state: AgentState) -> AgentState:
    """Classify and validate request after enrichment"""
    validator = RequestValidator()
    
    result = validator.validate_and_classify(
        request=state["request"],
        client_context=state["client_context"],
        file_summaries=state.get("file_summaries"),
        website_content=state.get("website_content")
    )
    
    return {
        **state,
        **result,
        "needs_admin_review": not result["is_request_complete"]
    }
```

3. Admin Task Creation Node

```python
from clickup import ClickUp
from typing import Dict

# Constants
THEO_LIST_ID = "your-theo-list-id"  # Admin review list

def create_admin_task(state: AgentState) -> AgentState:
    """Create task in admin list when request needs clarification"""
    
    clickup = ClickUp(api_token=os.getenv("CLICKUP_API_TOKEN"))
    
    # Format missing information for task description
    missing_info_list = "\n".join([f"- {item}" for item in state["missing_information"]])
    
    task_description = f"""# Request Needs Clarification

**Original Request:**
{state["request"]}

**Classified As:** {state["request_category"]}
{f"**Subcategories:** {', '.join(state['request_subcategories'])}" if state['request_subcategories'] else ""}

**Missing Information:**
{missing_info_list}

**Available Context:**
- Client: {state['client_context'].get('client_name', 'Unknown')}
- Files Attached: {'Yes' if state.get('file_summaries') else 'No'}
- Website Context: {'Yes' if state.get('website_content') else 'No'}

**Next Steps:**
1. Contact client for clarification
2. Once info is gathered, create a new request with complete details
"""
    
    task_data = {
        "name": f"Clarify Request: {state['request'][:50]}...",
        "description": task_description,
        "tags": [
            "needs-clarification",
            state["request_category"],
            "admin-review"
        ],
        "priority": 3,  # Normal priority
        "status": "to do"
    }
    
    response = clickup.create_task(THEO_LIST_ID, **task_data)
    
    return {
        **state,
        "admin_task_id": response["id"]
    }
```

5. Updated Workflow Graph

```python
from langgraph.graph import StateGraph, END

# Conditional routing function
def route_after_validation(state: AgentState) -> Literal["create_admin_task", "architect"]:
    """Route based on request completeness"""
    if state["needs_admin_review"]:
        return "create_admin_task"
    return "architect"

def should_retry_or_escalate(state: AgentState) -> Literal["architect", "escalate", "create_task"]:
    """Route based on QA results"""
    if state["qa_approved"]:
        return "create_task"
    
    if state["qa_attempts"] >= 3:
        return "escalate"
    
    return "architect"

# Build the graph
workflow = StateGraph(AgentState)

# Add all nodes
workflow.add_node("enrichment", enrichment_node)  # Your existing enrichment
workflow.add_node("validate", validate_request)
workflow.add_node("create_admin_task", create_admin_task)
workflow.add_node("architect", architect_plan)
workflow.add_node("qa_review", qa_review)
workflow.add_node("create_task", create_clickup_task)
workflow.add_node("escalate", escalate_to_clickup)

# Define flow
workflow.set_entry_point("enrichment")

# Enrichment -> Validate
workflow.add_edge("enrichment", "validate")

# Validate -> Admin Task OR Architect
workflow.add_conditional_edges(
    "validate",
    route_after_validation,
    {
        "create_admin_task": "create_admin_task",
        "architect": "architect"
    }
)

# Admin task ends the workflow
workflow.add_edge("create_admin_task", END)

# Continue normal flow
workflow.add_edge("architect", "qa_review")

workflow.add_conditional_edges(
    "qa_review",
    should_retry_or_escalate,
    {
        "architect": "architect",
        "escalate": "escalate",
        "create_task": "create_task"
    }
)

workflow.add_edge("create_task", END)
workflow.add_edge("escalate", END)

app = workflow.compile()
```

6. TDD Test Suite

```python
import pytest
from unittest.mock import Mock, patch

class TestRequestValidation:
    
    def test_blog_post_request_complete(self):
        """Test complete blog post request is classified correctly"""
        validator = RequestValidator()
        
        result = validator.validate_and_classify(
            request="Write a blog post about 'Best WordPress Security Plugins 2024' targeting keyword 'wordpress security', 1500 words, include comparison table",
            client_context={"cms": "wordpress", "industry": "tech"},
            website_content="Blog at /blog/"
        )
        
        assert result["request_category"] == RequestCategory.BLOG_POST
        assert result["is_request_complete"] == True
        assert len(result["missing_information"]) == 0
    
    def test_vague_bug_report_incomplete(self):
        """Test vague bug report is marked incomplete"""
        validator = RequestValidator()
        
        result = validator.validate_and_classify(
            request="The contact form isn't working",
            client_context={"cms": "wordpress"},
            website_content="Contact page at /contact/"
        )
        
        assert result["request_category"] == RequestCategory.BUG_FIX
        assert result["is_request_complete"] == False
        assert len(result["missing_information"]) > 0
        assert any("what" in item.lower() or "error" in item.lower() 
                  for item in result["missing_information"])
    
    def test_multi_category_classification(self):
        """Test request that spans multiple categories"""
        validator = RequestValidator()
        
        result = validator.validate_and_classify(
            request="Add a new Services page with SEO optimization for 'web development services'",
            client_context={"cms": "wordpress"},
        )
        
        assert result["request_category"] == RequestCategory.NEW_PAGE
        assert RequestCategory.SEO_OPTIMIZATION in result["request_subcategories"]
    
    def test_admin_task_created_for_incomplete_request(self):
        """Test admin task is created when validation fails"""
        initial_state = {
            "request": "Fix the thing",
            "client_context": {},
            "file_summaries": [],
            "website_content": "",
            "qa_attempts": 0
        }
        
        result = app.invoke(initial_state)
        
        assert result["needs_admin_review"] == True
        assert result["admin_task_id"] is not None
        assert result["is_request_complete"] == False
        assert "clickup_task_id" not in result  # Workflow should end
    
    def test_complete_request_skips_admin_task(self):
        """Test complete request goes straight to architect"""
        initial_state = {
            "request": "Create blog post 'Top 10 WordPress Plugins' targeting 'best wordpress plugins', 1200 words",
            "client_context": {"cms": "wordpress"},
            "file_summaries": [],
            "website_content": "Blog at /blog/",
            "qa_attempts": 0
        }
        
        with patch('your_module.ReviewAgent.review_plan') as mock_qa:
            mock_qa.return_value = {"content": "APPROVE", "model": "claude", "usage": {}}
            
            result = app.invoke(initial_state)
            
            assert result["is_request_complete"] == True
            assert result.get("admin_task_id") is None
            assert result["clickup_task_id"] is not None
```

7. Future feature: Specialized Agent Routing

When you're ready to add specialized agents, you can route based on category:

```python
def route_to_specialized_agent(state: AgentState) -> Literal["blog_agent", "seo_agent", "bug_fix_agent", "general_architect"]:
    """Route to specialized agent based on category"""
    category = state["request_category"]
    
    routing_map = {
        RequestCategory.BLOG_POST: "blog_agent",
        RequestCategory.SEO_OPTIMIZATION: "seo_agent",
        RequestCategory.BUG_FIX: "bug_fix_agent",
    }
    
    return routing_map.get(category, "general_architect")
```

# Then in your workflow:
```python
workflow.add_conditional_edges(
    "validate",
    lambda state: "create_admin_task" if state["needs_admin_review"] else "route_agents",
    {
        "create_admin_task": "create_admin_task",
        "route_agents": ...  # Your routing logic
    }
)
```

This approach keeps the workflow as a clear DAG while building in the flexibility for future specialized agents, all driven by the domain model (request classification).
# Environment

Use `python3` and `pip3` to run the code.

Clickup.com API documentation is here: https://developer.clickup.com/reference/

# Agency AI Orchestrator: System Design

## 1. Logic Flow
The system operates as a Directed Acyclic Graph (DAG) with a self-correction loop (state machine).

## 2. Agent Roles
- **Enricher:** Maps `client_id` to Airtable records. Retrieves `tech_stack`, `brand_identity`, and `list_id`.
- **Architect:** The "Technical Writer." Converts client requests into dev-ready tasks using a strict Pydantic schema.
- **QA Reviewer:** The "Gatekeeper." Checks for Mermaid syntax validity and presence of technical constraints.

## 3. Intermediate Representation (IR)
All tasks must contain:
- Markdown headers for scannability.
- Mermaid.js diagrams for logic flows.
- ClickUp-ready checklists.

## 4. State Management
`AgentState` tracks the request, fetched context, iteration count (max 3), and QA critique strings.
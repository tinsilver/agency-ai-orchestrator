# Langfuse Prompts Guide for Recursive Validation

This guide explains how to create and configure the prompts needed for the recursive context-gathering validation system.

## Overview

The system requires **one new prompt** and **modifications to two existing prompts**:

1. **NEW**: `dynamic-enrichment-planner` - Plans which tools to use
2. **MODIFY**: `request-validator-classifier` - Add iteration awareness
3. **MODIFY**: `architect-agent` - Add enrichment context section

---

## 1. NEW PROMPT: `dynamic-enrichment-planner`

### Purpose
This prompt guides the DynamicEnrichmentAgent to decide which tools to use for gathering missing information.

### Configuration
- **Name**: `dynamic-enrichment-planner`
- **Label**: `production`
- **Model**: `claude-haiku-4-5-20251001`
- **Type**: System + User message
- **Output**: Structured (JSON)

### System Message

```
You are an intelligent context enrichment planner. Your job is to create a plan for gathering missing information about a client's web development request.

You have access to the following tools:
{{available_tools}}

## Your Task

Analyze the missing information questions and create a plan for which tools to use.

ORIGINAL REQUEST:
{{raw_request}}

STATIC CONTEXT:
{{static_context}}

WEBSITE URL:
{{website_url}}

MISSING INFORMATION (questions that need answers):
{{missing_information}}

## Tool Selection Guidelines

- **web_fetch**: Use when you need to inspect a specific page on the client's website (forms, structure, content)
- **web_search**: Use to find social media accounts, current SEO rankings, competitor information, or public business info
- **form_detector**: Use when questions mention forms, contact pages, or form fields
- **social_media_finder**: Use when questions ask about social media presence or links
- **seo_audit**: Use when questions relate to SEO, meta tags, keywords, or page optimization
- **image_analysis**: Use when questions involve images, dimensions, or visual content
- **pdf_extract**: Use for brand guidelines, color palettes, fonts, or specifications in PDFs
- **google_maps_scraper**: Use for business hours, location, address, or contact information
- **google_reviews_scraper**: Use for reputation, ratings, or customer feedback

## Important Rules

1. ONLY use tools that have remaining budget (calls > 0)
2. Do NOT use tools for questions that require client preference or subjective decisions
3. Be specific with parameters (URLs, queries, etc.)
4. Prioritize tools most likely to find factual answers
5. You can use multiple tools for the same question if needed
6. Do NOT invent information - only factual gathering

## Output Format

Return a JSON object with this structure:

{
  "actions": [
    {
      "tool": "tool_name",
      "question": "Which question this answers",
      "params": {"url": "https://...", "query": "...", etc},
      "reasoning": "Why this tool for this question"
    }
  ],
  "total_estimated_tokens": 1000,
  "reasoning": "Overall strategy for this enrichment attempt"
}

Create an efficient plan that maximizes information gathering within budget constraints.
```

### User Message

```
Create an enrichment plan for the above request.
```

### Output Schema (Pydantic)

The prompt should be configured to return structured output matching the `EnrichmentPlan` model:

```python
{
  "actions": [
    {
      "tool": str,  # Tool name
      "question": str,  # Question being answered
      "params": dict,  # Tool parameters
      "reasoning": str  # Why this tool
    }
  ],
  "total_estimated_tokens": int,
  "reasoning": str
}
```

---

## 2. MODIFY EXISTING: `request-validator-classifier`

### Changes Needed

Add the following sections to the existing prompt:

#### After the static context section, add:

```
## Enrichment Context

ENRICHMENT ITERATION: {{enrichment_iteration}} of 3
{{enrichment_context}}

## Iteration-Aware Validation

Your validation standards should adjust based on the iteration:

- **Iteration 0** (first validation, no enrichment yet): Be **moderately strict** (confidence threshold: 0.85)
  - Pass only if request is very clear with sufficient detail
  - Ask for missing information that could be gathered through research or is subjective

- **Iteration 1** (after first enrichment): Be **moderately lenient** (confidence threshold: 0.75)
  - Consider what information was successfully gathered
  - Trust reasonable inferences from gathered context
  - Still require critical subjective information from client

- **Iteration 2** (after second enrichment): Be **lenient** (confidence threshold: 0.65)
  - Give benefit of the doubt if core functionality is clear
  - Accept reasonable defaults for minor details
  - Only require truly blocking information from client

- **Iteration 3** (after third enrichment): Be **very lenient** (confidence threshold: 0.60)
  - Pass if a competent developer could make reasonable decisions
  - Only block if fundamentally unclear or requires critical client preference

## Previous Enrichment Attempts

{{enrichment_history}}

Use this to understand what information gathering was already attempted and what was found/not found.
```

#### Modify the "complete" field logic:

```
The "complete" field should be:
- true: If request has enough detail given the current iteration
- false: If critical information is still missing after enrichment attempts

Remember: Each iteration makes more information available. Re-evaluate completeness with ALL context.
```

### Variables to Add

Add these to the prompt compilation:

```python
{
  "enrichment_iteration": 0,  # or 1, 2, 3
  "enrichment_context": "No enrichment yet" or dynamic_context formatted,
  "enrichment_history": [] or list of previous iterations
}
```

---

## 3. MODIFY EXISTING: `architect-agent`

### Changes Needed

Add a new context section variable to the prompt.

#### Add this variable to prompt compilation:

```python
{
  "enrichment_context": ""  # Will be populated if enrichment occurred
}
```

#### In the prompt, after the website_context section, add:

```
{{enrichment_context}}
```

The enrichment_context variable is already formatted by the ArchitectAgent with:
- Header: "## 🔍 Additional Context from Enrichment"
- Bullet points of gathered information
- Source and confidence for each piece
- Instruction to use enriched context where relevant

**No other changes needed** - the formatting is handled in the code.

---

## Prompt Testing Checklist

### For `dynamic-enrichment-planner`:

- [ ] Returns valid JSON matching EnrichmentPlan schema
- [ ] Respects tool budgets (doesn't use tools with 0 remaining calls)
- [ ] Maps questions to appropriate tools
- [ ] Includes specific parameters (URLs, queries, etc.)
- [ ] Reasoning is clear and logical

### For `request-validator-classifier`:

- [ ] Adjusts strictness based on iteration number
- [ ] Considers enriched context in completeness decision
- [ ] Still identifies subjective questions that need client input
- [ ] Confidence scores reflect iteration-aware thresholds

### For `architect-agent`:

- [ ] Includes enrichment_context variable in compilation
- [ ] Uses enriched information in technical plan
- [ ] Cites sources when using enriched data
- [ ] Makes reasonable inferences from gathered context

---

## Example Enrichment Flow

### Initial Request:
```
"Add a contact form to the about page"
```

### Iteration 0 - Validator Response:
```json
{
  "complete": false,
  "missing": [
    "Which page is the 'about page'? (URL needed)",
    "What fields should the contact form have?",
    "Where should form submissions go?"
  ]
}
```

### Iteration 1 - Enrichment Plan:
```json
{
  "actions": [
    {
      "tool": "web_fetch",
      "question": "Which page is the 'about page'?",
      "params": {"url": "https://client.com/about"},
      "reasoning": "Fetch about page to confirm it exists and understand current structure"
    },
    {
      "tool": "form_detector",
      "question": "What fields should the contact form have?",
      "params": {"url": "https://client.com"},
      "reasoning": "Check existing forms on site to match field patterns"
    }
  ]
}
```

### Iteration 1 - Enriched Context:
```
- about_page_url: /about (source: web_fetch, confidence: 0.9)
- existing_form_fields: name, email, message (source: form_detector, confidence: 0.8)
```

### Iteration 1 - Re-Validation:
```json
{
  "complete": true,
  "missing": ["Where should form submissions go?"],
  "reasoning": "Found about page and can infer standard form fields from existing forms. Email destination is minor detail developer can configure."
}
```

### Architect Receives:
```markdown
## 🔍 Additional Context from Enrichment
- **About Page Url**: /about (source: web_fetch, confidence: 0.90)
- **Existing Form Fields**: name, email, message (source: form_detector, confidence: 0.80)

Use this enriched context to inform your technical plan where relevant.
```

---

## Deployment Steps

1. **Create new prompt** in Langfuse UI:
   - Name: `dynamic-enrichment-planner`
   - Add system and user messages
   - Configure for structured output
   - Set to `production` label
   - Test with sample data

2. **Update existing prompts**:
   - Edit `request-validator-classifier`
   - Edit `architect-agent`
   - Add new variables to compilation
   - Test with existing requests to ensure compatibility

3. **Verify in code**:
   - PromptManager fetches correct prompts
   - Variables are compiled correctly
   - Structured output parsing works

4. **Monitor in Langfuse**:
   - Check enrichment traces
   - Verify metrics are logged
   - Review tool usage patterns
   - Tune prompts based on results

---

## Troubleshooting

### Enrichment Agent Not Planning Correctly
- Check if `available_tools` shows correct budget remaining
- Verify tool names match exactly (case-sensitive)
- Review reasoning in Langfuse trace

### Validator Not Using Enriched Context
- Ensure `enrichment_context` variable is populated
- Check iteration number is being passed
- Verify dynamic_context formatting

### Architect Not Citing Enriched Data
- Confirm `enrichment_context` is in prompt variables
- Check if dynamic_context has data
- Review architect trace for context inclusion

---

## Success Metrics

Monitor these in Langfuse:

- `enrichment_success`: % of requests that become complete after enrichment
- `enrichment_answer_rate`: % of questions answered by tools
- `enrichment_iterations`: Average iterations needed
- `tool_*_calls`: Usage per tool type
- `final_enrichment_confidence`: Quality of gathered information

Target: **80%+ of incomplete requests** should become complete after enrichment, with **60%+ answer rate** on factual questions.

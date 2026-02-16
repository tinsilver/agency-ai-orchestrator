# Admin Task Feature Parity

## Summary
Updated `create_admin_task_node` to have feature parity with `clickup_push_node`.

## Changes Made to `create_admin_task_node` ([app/graph.py:192-273](app/graph.py#L192-L273))

### 1. **Priority Setting** ✅

**Before:**
```python
result = await clickup_service.create_task(
    list_id=THEO_LIST_ID,
    name=title,
    description=description,
    tags=tags,
)
```

**After:**
```python
# Get client priority from state
client_priority = state.get("client_priority")

# Determine priority (default to High if not specified)
priority_str = client_priority if client_priority else "High"
priority = map_priority_to_clickup(priority_str)

result = await clickup_service.create_task(
    list_id=THEO_LIST_ID,
    name=title,
    description=description,
    tags=tags,
    priority=priority  # NEW
)
```

**Logic:**
- Uses client's requested priority if provided
- **Defaults to "High"** for admin review tasks (needs attention)
- Maps to ClickUp API format: High = 2

### 2. **Priority in Description** ✅

**Added to markdown description:**
```markdown
## Classification
- **Category:** bug_fix
- **Subcategories:** none
- **Client Priority:** Normal  ← NEW
```

Shows the client's requested priority so admin can see their urgency expectation.

### 3. **Checklist Creation** ✅

**New feature:**
```python
# Add checklist for missing information items
if task_id and missing:
    checklist_res = await clickup_service.create_checklist(task_id, "Information to Gather")
    checklist_id = checklist_res.get("checklist", {}).get("id")

    if checklist_id:
        for item in missing:
            await clickup_service.create_checklist_item(checklist_id, item)
```

Creates a checklist titled **"Information to Gather"** with each missing item as a checkbox.

**Example:**
```
☐ What is the desired behavior when the form submits?
☐ Should validation happen on client or server side?
☐ What error messages should be shown?
```

### 4. **Enhanced Logging** ✅

**Before:**
```python
logs["admin_task"] = {
    "id": task_id,
    "url": task_url,
    "name": title,
}
```

**After:**
```python
logs["admin_task"] = {
    "id": task_id,
    "url": task_url,
    "name": title,
    "payload_sent": {
        "name": title,
        "description": description,
        "tags": tags,
        "priority": priority,          # NEW
        "priority_string": priority_str,  # NEW
    }
}
```

Matches the logging format of `clickup_push_node` for consistency in Langfuse traces.

### 5. **History Update** ✅

**Before:**
```python
history.append(f"Created admin review task in ClickUp: {task_url or task_id}")
```

**After:**
```python
history.append(f"Created admin review task in ClickUp (Priority: {priority_str}): {task_url or task_id}")
```

Shows priority in workflow history for debugging.

## Feature Comparison (After Changes)

| Feature | `clickup_push_node` | `create_admin_task_node` |
|---------|---------------------|--------------------------|
| **Priority** | ✅ From architect | ✅ From client (default: High) |
| **Checklist** | ✅ "Definition of Done" | ✅ "Information to Gather" |
| **Attachments** | ✅ Uploaded | ✅ Uploaded |
| **Tags** | ✅ Dynamic | ✅ Hardcoded + category |
| **Priority in Description** | ✅ With reasoning | ✅ Client priority shown |
| **Detailed Logging** | ✅ Full payload | ✅ Full payload |

## Testing

### Test Scenario: Incomplete Request

**Input:**
```json
{
  "client_id": "testclient.com",
  "client_priority": "Normal",
  "client_category": "bug_fix",
  "request_text": "Fix the contact form"
}
```

**Expected Behavior:**
1. Request classified as incomplete (missing details)
2. Admin task created with:
   - ✅ Priority: **Normal** (from client)
   - ✅ Checklist: Items for missing information
   - ✅ Description: Shows client priority
   - ✅ Tags: `["needs-clarification", "bug_fix", "agency-ai"]`

### Test Scenario: Incomplete Request (No Priority Specified)

**Input:**
```json
{
  "client_id": "testclient.com",
  "client_priority": null,
  "request_text": "Update the homepage"
}
```

**Expected Behavior:**
1. Admin task created with:
   - ✅ Priority: **High** (default for admin tasks)
   - ✅ Description shows: "Client Priority: Not specified"

## Rationale for Default Priority

**Why "High" for admin tasks?**
- Admin review tasks need attention to unblock the client
- Setting them as "High" ensures they don't get lost in the backlog
- Client's actual priority preference is preserved in description
- Admin can adjust priority based on full context

## Backward Compatibility

✅ **Fully backward compatible**
- All changes are additive
- Existing admin tasks continue to work
- If `client_priority` is not in state, defaults to "High"
- Checklist only created if `missing` items exist

## Related Files

- [app/graph.py:192-273](app/graph.py#L192-L273) - `create_admin_task_node` function
- [app/graph.py:349-447](app/graph.py#L349-L447) - `clickup_push_node` function (reference)
- [app/services/clickup.py:133-187](app/services/clickup.py#L133-L187) - ClickUp service with priority support

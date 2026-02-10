import os
import httpx
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langfuse import observe

load_dotenv()

class ClickUpService:
    def __init__(self):
        self.api_key = os.getenv("CLICKUP_API_KEY")
        self.team_id = os.getenv("CLICKUP_TEAM_ID")  # Workspace ID
        self.api_url = "https://api.clickup.com/api/v2"
        self.headers = {"Authorization": self.api_key} if self.api_key else {}

    async def get_spaces(self) -> List[Dict[str, Any]]:
        """Get all spaces for the team."""
        if not self.api_key: return []
        url = f"{self.api_url}/team/{self.team_id}/space"
        return await self._get_paginated(url, "spaces")

    async def get_folders(self, space_id: str) -> List[Dict[str, Any]]:
        """Get all folders in a space."""
        if not self.api_key: return []
        url = f"{self.api_url}/space/{space_id}/folder"
        return await self._get_paginated(url, "folders")

    async def get_lists(self, folder_id: str) -> List[Dict[str, Any]]:
        """Get all lists in a folder."""
        if not self.api_key: return []
        url = f"{self.api_url}/folder/{folder_id}/list"
        return await self._get_paginated(url, "lists")
        
    @observe(name="clickup-get-tasks")
    async def get_tasks(self, list_id: str, include_closed: bool = False) -> List[Dict[str, Any]]:
        """Get tasks in a list."""
        if not self.api_key: return []
        url = f"{self.api_url}/list/{list_id}/task"
        params = {"include_closed": str(include_closed).lower()}
        return await self._get_paginated(url, "tasks", params)

    async def _get_paginated(self, url: str, key: str, params: Dict = None) -> List[Any]:
        """Helper for simple GET requests wrapping results."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get(key, [])
            except httpx.HTTPError as e:
                print(f"Error fetching from {url}: {e}")
                return []

    @observe(name="clickup-get-task-details")
    async def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch task details, including custom fields. 
        This is now used to retrieve Client Context (Tech Stack, Brand).
        """
        if not self.api_key:
             print("Warning: ClickUp credentials not found via env.")
             return {
                 "name": "Test Client",
                 "custom_fields": [
                     {"name": "Tech Stack", "value": "Python, React"},
                     {"name": "Brand Guidelines", "value": "Dark Mode"}
                 ]
             }

        url = f"{self.api_url}/task/{task_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                print(f"Error fetching ClickUp task {task_id}: {e}")
                return None

    @observe(name="clickup-create-task")
    async def create_task(self, list_id: str, name: str, description: str, tags: List[str] = []) -> Dict[str, Any]:
        """
        Create a task in a specific ClickUp List.
        """
        if not self.api_key:
             print("Warning: ClickUp credentials not found via env.")
             return {"id": "mock-task-id", "url": "http://mock-clickup-url"}

        url = f"{self.api_url}/list/{list_id}/task"
        payload = {
            "name": name,
            "markdown_content": description,
            "tags": tags
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                print(f"Error creating ClickUp task: {e}")
                return {"error": str(e)}

    async def create_checklist(self, task_id: str, name: str) -> Dict[str, Any]:
        """Create a checklist on a task."""
        url = f"{self.api_url}/task/{task_id}/checklist"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers, json={"name": name})
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                print(f"Error creating checklist: {e}")
                return {}

    async def create_checklist_item(self, checklist_id: str, name: str) -> Dict[str, Any]:
        """Add an item to a checklist."""
        url = f"{self.api_url}/checklist/{checklist_id}/checklist_item"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=self.headers, json={"name": name})
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                print(f"Error creating checklist item: {e}")
                return {}

    async def create_task_attachment(self, task_id: str, file_content: bytes, filename: str, content_type: str = None) -> Dict[str, Any]:
        """Upload a file as an attachment to a task."""
        if not self.api_key:
             print("Warning: ClickUp credentials not found via env.")
             return {"id": "mock-attachment-id", "url": "http://mock-attachment-url"}

        url = f"{self.api_url}/task/{task_id}/attachment"
        
        # Files dict for httpx
        files = {
            "attachment": (filename, file_content, content_type)
        }
        
        # Headers for attachment upload (do not set Content-Type, httpx handles it)
        # However, we must pass the Authorization token
        headers = {"Authorization": self.api_key}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, files=files)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"Error uploading attachment {filename}: {e}")
                return {"error": str(e)}

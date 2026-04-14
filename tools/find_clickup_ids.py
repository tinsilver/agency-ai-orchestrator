import asyncio
import os
import sys

# Ensure app can be imported
sys.path.append(os.getcwd())

from app.services.clickup import ClickUpService

async def find_ids():
    service = ClickUpService()
    print("Fetching Spaces...")
    spaces = await service.get_spaces()
    
    targets = {
        "Operations": {
            "found": False, 
            "folderless_lists": ["Site Parameters", "Client Configurations", "New Requests"]
        },
        "Virtual Assistants": {
            "found": False, 
            "folders": ["Active"], 
            "lists": ["Dinesh - Upwork"]
        }
    }
    
    results = {}

    for space in spaces:
        name = space['name']
        print(f"Space: {name} ({space['id']})")
        
        if name in targets:
            targets[name]["found"] = True
            print(f"  -> Found Target Space: {name}")
            
            # 1. Search Folderless Lists First
            if "folderless_lists" in targets[name]:
                space_lists = await service.get_space_lists(space['id'])
                for slst in space_lists:
                    slname = slst['name']
                    print(f"  Space List: {slname} ({slst['id']})")
                    if slname in targets[name]["folderless_lists"]:
                        print(f"    -> FOUND TARGET LIST: {slname} ID: {slst['id']}")
                        results[slname] = slst['id']

            # 2. Get Folders
            if "folders" in targets[name]:
                folders = await service.get_folders(space['id'])
                for folder in folders:
                    fname = folder['name']
                    print(f"  Folder: {fname} ({folder['id']})")
                    
                    if fname in targets[name].get("folders", []):
                        print(f"    -> Found Target Folder: {fname}")
                        
                        # Get Lists
                        if "lists" in targets[name]:
                            lists = await service.get_lists(folder['id'])
                            for lst in lists:
                                lname = lst['name']
                                print(f"    List: {lname} ({lst['id']})")
                                
                                if lname in targets[name].get("lists", []):
                                    print(f"      -> FOUND TARGET LIST: {lname} ID: {lst['id']}")
                                    results[lname] = lst['id']
    
    print("\n--- RESULTS ---")
    print(results)
    return results

if __name__ == "__main__":
    asyncio.run(find_ids())

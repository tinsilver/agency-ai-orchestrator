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
        "Clients": {"found": False, "folders": ["Active"], "lists": ["Site Parameters"]},
        "Virtual Assistants": {"found": False, "folders": ["Active"], "lists": ["Dinesh - Upwork"]}
    }
    
    results = {}

    for space in spaces:
        name = space['name']
        print(f"Space: {name} ({space['id']})")
        
        if name in targets:
            targets[name]["found"] = True
            print(f"  -> Found Target Space: {name}")
            
            # Get Folders
            folders = await service.get_folders(space['id'])
            for folder in folders:
                fname = folder['name']
                print(f"  Folder: {fname} ({folder['id']})")
                
                if fname in targets[name]["folders"]:
                    print(f"    -> Found Target Folder: {fname}")
                    
                    # Get Lists
                    lists = await service.get_lists(folder['id'])
                    for lst in lists:
                        lname = lst['name']
                        print(f"    List: {lname} ({lst['id']})")
                        
                        if lname in targets[name]["lists"]:
                            print(f"      -> FOUND TARGET LIST: {lname} ID: {lst['id']}")
                            results[lname] = lst['id']

            # Check for folderless lists if necessary (not common in this structure but possible)
    
    print("\n--- RESULTS ---")
    print(results)
    return results

if __name__ == "__main__":
    asyncio.run(find_ids())

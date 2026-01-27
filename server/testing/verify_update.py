import asyncio
import httpx
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def verify_update():
    print("Testing Conversation Update API...")
    async with httpx.AsyncClient() as client:
        # 1. Login
        # Assuming we can use the test user logic or bypass auth for local test if needed.
        # But our endpoints require auth.
        # Let's register/login a temp user.
        base_url = "http://localhost:3000/api"
        email = f"updater_{os.urandom(4).hex()}@example.com"
        password = "password123"
        
        # Register
        reg_res = await client.post(f"{base_url}/auth/register", json={
            "email": email, "password": password, "full_name": "Updater"
        })
        if reg_res.status_code != 200:
            print(f"Registration failed: {reg_res.text}")
            return

        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create Conversation
        create_res = await client.post(
            f"{base_url}/conversations", 
            json={"title": "Original Title"},
            headers=headers
        )
        conv = create_res.json()
        conv_id = conv["id"]
        print(f"Created conversation: {conv_id}")
        
        # 3. Create Project
        proj_res = await client.post(
            f"{base_url}/projects",
            json={"name": "New Project", "description": "Test"},
            headers=headers
        )
        project = proj_res.json()
        project_id = project["id"]
        print(f"Created project: {project_id}")
        
        # 4. Update Conversation Project ID
        print(f"Updating conversation {conv_id} with project_id {project_id}...")
        update_res = await client.patch(
            f"{base_url}/conversations/{conv_id}",
            json={"project_id": project_id, "title": "Updated Title"},
            headers=headers
        )
        
        if update_res.status_code != 200:
            print(f"Update failed: {update_res.text}")
            return
            
        updated = update_res.json()
        
        # 5. Verify
        assert updated["project_id"] == project_id
        assert updated["title"] == "Updated Title"
        print("SUCCESS: Conversation updated correctly!")

if __name__ == "__main__":
    asyncio.run(verify_update())

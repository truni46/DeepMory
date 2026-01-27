import asyncio
import httpx
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def verify_delete():
    print("Testing Conversation Delete API...")
    async with httpx.AsyncClient() as client:
        base_url = "http://localhost:3000/api"
        # 1. Login/Register (Using unique email to avoid conflict)
        email = f"deleter_{os.urandom(4).hex()}@example.com"
        password = "password123"
        
        reg_res = await client.post(f"{base_url}/auth/register", json={
            "email": email, "password": password, "full_name": "Deleter"
        })
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create Conversation
        create_res = await client.post(
            f"{base_url}/conversations", 
            json={"title": "To Be Deleted"},
            headers=headers
        )
        conv_id = create_res.json()["id"]
        print(f"Created conversation: {conv_id}")
        
        # 3. Delete Conversation
        print(f"Deleting conversation {conv_id}...")
        del_res = await client.delete(
            f"{base_url}/conversations/{conv_id}",
            headers=headers
        )
        
        assert del_res.status_code == 204, f"Delete failed: {del_res.status_code}"
        print("Delete request successful (204)")
        
        # 4. Verify it's gone
        get_res = await client.get(
            f"{base_url}/conversations/{conv_id}",
            headers=headers
        )
        assert get_res.status_code == 404
        print("SUCCESS: Conversation successfully deleted and not found!")

if __name__ == "__main__":
    asyncio.run(verify_delete())

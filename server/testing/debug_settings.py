import asyncio
import httpx
import sys

async def debug_settings():
    print("Debugging Settings Persistence...")
    async with httpx.AsyncClient() as client:
        base_url = "http://localhost:3000/api"
        
        # 1. Login
        email = "agentic_rag_demo@example.com"
        password = "password123"
        
        login_res = await client.post(f"{base_url}/auth/login", data={
            "username": email, "password": password
        })
        
        if login_res.status_code != 200:
            print(f"Login Failed: {login_res.text}")
            return

        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Get Initial Settings
        print("\n--- Initial Settings ---")
        get_res = await client.get(f"{base_url}/settings", headers=headers)
        print(get_res.json())
        
        # 3. Update Settings
        print("\n--- Updating Settings ---")
        new_settings = {"theme": "dark", "communication_mode": "websocket"}
        update_res = await client.put(f"{base_url}/settings", json=new_settings, headers=headers)
        print(f"Update Status: {update_res.status_code}")
        print(update_res.json())
        
        # 4. Verify Persistence (Fetch again)
        print("\n--- Verifying Persistence ---")
        verify_res = await client.get(f"{base_url}/settings", headers=headers)
        final_settings = verify_res.json()
        print(final_settings)
        
        if final_settings.get("theme") == "dark":
            print("\nSUCCESS: Settings persisted!")
        else:
            print("\nFAILURE: Settings not persisted.")

if __name__ == "__main__":
    asyncio.run(debug_settings())

import asyncio
import httpx
import sys
import os

async def debug_messages():
    print("Debugging Message Retrieval...")
    async with httpx.AsyncClient() as client:
        base_url = "http://localhost:3000/api"
        
        # 1. Login
        email = "agentic_rag_demo@example.com"
        password = "password123"
        
        # Login
        login_res = await client.post(f"{base_url}/auth/login", data={
            "username": email, "password": password
        })
        
        if login_res.status_code != 200:
            print(f"Login Failed: {login_res.text}")
            return

        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Get Conversations
        conv_res = await client.get(f"{base_url}/conversations", headers=headers)
        conversations = conv_res.json()
        
        if not conversations:
            print("No conversations found!")
            return

        print(f"Found {len(conversations)} conversations.")
        target_conv = conversations[0]
        print(f"Checking conversation: {target_conv['title']} ({target_conv['id']})")
        
        # 3. Get History
        history_res = await client.get(f"{base_url}/messages/{target_conv['id']}", headers=headers)
        
        if history_res.status_code != 200:
            print(f"History Fetch Failed: {history_res.text}")
            return
            
        messages = history_res.json()
        print(f"\nRetrieved {len(messages)} messages:")
        for msg in messages:
            print(f"[{msg['role']}] {msg['content'][:50]}...")

if __name__ == "__main__":
    asyncio.run(debug_messages())

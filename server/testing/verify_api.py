import asyncio
import httpx
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app
from config.database import db

async def test_api_flow():
    print("Starting API Flow Verification (Async)...")
    
    # Initialize DB (Simulate Startup)
    await db.connect()
    
    # Base URL is required for AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as client:
        
        # 1. Register
        email = "api_async_user@example.com"
        password = "securepassword"
        print(f"Registering {email}...")
        response = await client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "username": "APIAsyncUser"
        })
        
        if response.status_code == 400 and "already registered" in response.text:
            print("User already exists, logging in...")
            # Login
            response = await client.post("/api/auth/login", data={
                "username": email,
                "password": password
            })
        
        if response.status_code != 200:
            print(f"Auth failed: {response.text}")
            return

        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Authenticated. Token: {token[:10]}...")

        # 2. Create Project
        print("Creating project...")
        response = await client.post("/api/projects", headers=headers, json={
            "name": "Async API Project",
            "description": "Created via AsyncClient"
        })
        assert response.status_code == 201, f"Create project failed: {response.text}"
        project_id = response.json()["id"]
        print(f"Project created: {project_id}")

        # 3. Create Conversation
        print("Creating conversation...")
        response = await client.post("/api/conversations", headers=headers, json={
            "title": "Async API Chat",
            "project_id": project_id
        })
        assert response.status_code == 201, f"Create conversation failed: {response.text}"
        conv_id = response.json()["id"]
        print(f"Conversation created: {conv_id}")

        # 3b. Create Independent Conversation (No Project)
        print("Creating conversation without project...")
        response = await client.post("/api/conversations", headers=headers, json={
            "title": "Independent Chat"
        })
        assert response.status_code == 201, f"Create independent conversation failed: {response.text}"
        indep_conv_id = response.json()["id"]
        print(f"Independent Conversation created: {indep_conv_id}")

        # 4. Stream Message
        print("Sending message...")
        # httpx stream
        async with client.stream("POST", "/api/messages/stream", headers=headers, json={
            "message": "Hello via Async API",
            "conversationId": conv_id,
            "projectId": project_id
        }) as response:
            assert response.status_code == 200, f"Stream failed: {response.text}"
            async for line in response.aiter_lines():
                if line:
                    print(f"Received chunk: {line[:50]}...")
                    break # Just confirm we got something

        print("API Verification SUCCESS!")
    
    # Shutdown DB
    await db.close()

if __name__ == "__main__":
    asyncio.run(test_api_flow())

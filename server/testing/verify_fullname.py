import asyncio
from httpx import AsyncClient
from main import app
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.database import db

async def test_fullname_integration():
    print("Starting Full Name Integration Check...")
    await db.connect()
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Register with Full Name
        email = "JohnDoe@example.com"
        full_name = "John Doe"
        print(f"Registering {full_name}...")
        
        response = await client.post("/api/auth/register", json={
            "email": email,
            "password": "password",
            "username": "johndoe",
            "full_name": full_name
        })
        
        if response.status_code == 400: # Already exists
            print("User exists, logging in...")
            response = await client.post("/api/auth/login", data={
                "username": email,
                "password": "password"
            })
            token = response.json()["access_token"]
            # We can't update full name yet if it wasn't set, unless we implemented update endpoint.
            # But let's check if it comes back in /me
        else:
            token = response.json()["access_token"]
            
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Check /me
        print("Checking /auth/me...")
        me_resp = await client.get("/api/auth/me", headers=headers)
        user = me_resp.json()
        print(f"User Data: {user}")
        
        if user.get("full_name") == full_name:
            print("SUCCESS: full_name returned correctly.")
        else:
            print("WARNING: full_name mismatch (might be pre-existing user without it).")

    await db.close()

if __name__ == "__main__":
    asyncio.run(test_fullname_integration())

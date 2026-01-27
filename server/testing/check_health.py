import asyncio
import httpx

async def check_health():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("http://localhost:3001/")
            print(f"Backend Status: {resp.status_code}")
            print(resp.json())
        except Exception as e:
            print(f"Backend check failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_health())

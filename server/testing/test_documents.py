import asyncio
import httpx
import os

# Configuration
API_URL = "http://localhost:3000/api"
TEST_USER = {
    "username": "agentic_rag_demo@example.com",
    "password": "password123"
}

async def run_test():
    async with httpx.AsyncClient() as client:
        print("1. Logging in...")
        response = await client.post(f"{API_URL}/auth/login", data=TEST_USER)
        if response.status_code != 200:
            print(f"Login failed: {response.text}")
            return
            
        token = response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful.")

        # Create dummy file
        with open("test_doc.txt", "w") as f:
            f.write("This is a test document content.")

        try:
            print("\n2. Uploading document...")
            with open('test_doc.txt', 'rb') as f:
                files = {'file': ('test_doc.txt', f, 'text/plain')}
                response = await client.post(f"{API_URL}/knowledge/upload", headers=headers, files=files)
            if response.status_code != 200:
                print(f"Upload failed: {response.text}")
                return
            
            doc = response.json()
            doc_id = doc['id']
            print(f"Upload successful. Doc ID: {doc_id}")

            print("\n3. Listing documents...")
            response = await client.get(f"{API_URL}/knowledge/documents", headers=headers)
            docs = response.json()
            print(f"Found {len(docs)} documents.")
            found = any(d['id'] == doc_id for d in docs)
            print(f"New document found in list: {found}")

            print("\n4. Deleting document...")
            response = await client.delete(f"{API_URL}/knowledge/documents/{doc_id}", headers=headers)
            if response.status_code == 200:
                print("Delete successful.")
            else:
                print(f"Delete failed: {response.text}")

            print("\n5. Verifying deletion...")
            response = await client.get(f"{API_URL}/knowledge/documents", headers=headers)
            docs = response.json()
            found = any(d['id'] == doc_id for d in docs)
            print(f"Document still exists: {found}")

        finally:
            if os.path.exists("test_doc.txt"):
                os.remove("test_doc.txt")

if __name__ == "__main__":
    asyncio.run(run_test())

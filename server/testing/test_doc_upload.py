import asyncio
import httpx
import os

# Configuration
API_URL = "http://localhost:3001/api"
TEST_USER = {
    "username": "agentic_rag_demo@example.com",
    "password": "password123"
}

TEST_DOC_FILENAME = "test_document.doc"

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

        # Create dummy .doc file (just text content for now, simulating binary)
        with open(TEST_DOC_FILENAME, "wb") as f:
            f.write(b"This is a dummy binary content simulating a .doc file.")

        doc_id = None
        try:
            print(f"\n2. Uploading {TEST_DOC_FILENAME}...")
            with open(TEST_DOC_FILENAME, 'rb') as f:
                files = {'file': (TEST_DOC_FILENAME, f, 'application/msword')}
                response = await client.post(f"{API_URL}/knowledge/upload", headers=headers, files=files)
            
            if response.status_code != 200:
                print(f"Upload failed: {response.text}")
                return
            
            doc = response.json()
            doc_id = doc['id']
            print(f"Upload successful. Doc ID: {doc_id}")
            print(f"File type recorded: {doc.get('file_type')}")

            print("\n3. Listing documents to verify...")
            response = await client.get(f"{API_URL}/knowledge/documents", headers=headers)
            docs = response.json()
            found_doc = next((d for d in docs if d['id'] == doc_id), None)
            
            if found_doc:
                print(f"Document found in list: {found_doc['filename']} ({found_doc['file_type']})")
            else:
                print("Document NOT found in list!")

        finally:
            # Cleanup
            if doc_id:
                print(f"\n4. Cleaning up (Deleting {doc_id})...")
                await client.delete(f"{API_URL}/knowledge/documents/{doc_id}", headers=headers)
            
            if os.path.exists(TEST_DOC_FILENAME):
                os.remove(TEST_DOC_FILENAME)

if __name__ == "__main__":
    asyncio.run(run_test())

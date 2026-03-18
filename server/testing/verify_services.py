import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uuid
from io import BytesIO
from config.database import db
from common.cache_service import cache_service
from modules.auth.service import auth_service
from modules.projects.service import project_service
from modules.conversations.service import conversation_service
from modules.chat.service import chat_service
from modules.chat.repository import message_repository
from modules.knowledge.service import document_service
from config.logger import logger

class MockFile:
    def __init__(self, content, filename):
        self.file = BytesIO(content)
        self.filename = filename

async def verify_system():
    logger.info("Starting System Verification...")
    
    # 1. Initialize Connections
    await db.connect()
    await cache_service.connect()
    
    try:
        # 2. Test Auth
        email = f"test_{uuid.uuid4()}@example.com"
        password = "password123"
        logger.info(f"Registering user: {email}")
        user = await auth_service.register_user(email, password, "TestUser")
        user_id = str(user['id'])
        logger.info(f"User registered: {user_id}")
        
        # 3. Test Project
        logger.info("Creating Project...")
        project = await project_service.create_project(user_id, "Test Project", "A project for verification")
        project_id = str(project['id'])
        logger.info(f"Project created: {project_id}")
        
        # 4. Test Document
        logger.info("Uploading Document...")
        mock_file = MockFile(b"This is a test document content about AI tutors.", "test_doc.txt")
        doc = await document_service.upload_document(user_id, project_id, mock_file, "test_doc.txt")
        logger.info(f"Document uploaded: {doc['id']}")
        
        # 5. Test Conversation
        logger.info("Creating Conversation...")
        conv = await conversation_service.create_conversation(user_id, "Verification Chat", project_id)
        conv_id = str(conv['id'])
        logger.info(f"Conversation created: {conv_id}")
        
        # 6. Test Message Flow
        logger.info("Sending Message...")
        message_content = "Hello, what is in the test document?"
        
        # Consume stream
        response_text = ""
        async for chunk in chat_service.process_message_flow(user_id, conv_id, message_content, project_id):
            response_text += chunk
            print(chunk, end="", flush=True)
        print("\n")
        logger.info("Message flow completed.")
        
        # 7. Check History
        history = await message_repository.get_by_conversation(conv_id)
        logger.info(f"Conversation History count: {len(history)}")
        assert len(history) >= 2 # User msg + Asst msg
        
        logger.info("Verification SUCCESS!")
        
    except Exception as e:
        logger.error(f"Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await cache_service.close()
        await db.close()

if __name__ == "__main__":
    asyncio.run(verify_system())

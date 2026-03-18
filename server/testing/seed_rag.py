import asyncio
import sys
import os

# Add server directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import db
from modules.auth.service import auth_service
from modules.conversations.repository import conversation_repository
from modules.chat.repository import message_repository

async def seed():
    # Connect to DB
    await db.connect()
    
    # 1. Create User
    email = "agentic_rag_demo@example.com"
    password = "password123"
    try:
        user = await auth_service.registerUser(email, password, "DemoUser", "Agentic Demo")
        print(f"User created: {user['id']}")
    except ValueError:
        # User might exist, lets fetch
        async with db.pool.acquire() as conn:
            user = dict(await conn.fetchrow("SELECT * FROM users WHERE email = $1", email))
            print(f"User found: {user['id']}")

    # 2. Create Conversation
    conversation = await conversation_repository.create(
        str(user['id']), 
        title="Agentic RAG Deep Dive"
    )
    print(f"Conversation created: {conversation['id']}")
    
    # 3. Add Messages
    turns = [
        ("user", "What is Agentic RAG?"),
        ("assistant", "Agentic RAG is an extension of standard Retrieval-Augmented Generation that introduces 'agentic' capabilities. Instead of a linear retrieve-then-generate process, an autonomous agent orchestrates the workflow. It can plan, search multiple sources, critique its own findings, and iteratively refine the answer."),
        ("user", "How does it differ from standard RAG?"),
        ("assistant", "Standard RAG is typically a single-pass pipeline: Query -> Embed -> Search -> Generate. It fails if the initial search is poor.\n\nAgentic RAG, however, is a loop. The agent can:\n1. **Reason**: Break down complex queries.\n2. **Tool Use**: Decide to use specific search tools, calculators, or APIs.\n3. **Reflection**: Check if the retrieved documents actually answer the question.\n4. **Iteration**: Re-search with better keywords if needed."),
        ("user", "Can you give an example workflow?"),
        ("assistant", "Sure! Here is a 'Self-RAG' workflow example:\n\n1. **Receive Query**: 'Who is the CEO of the company that acquired Slack?'\n2. **Plan**: Need to find (1) who acquired Slack, (2) CEO of that company.\n3. **Step 1**: Agent uses `search_tool('Slack acquisition')`. Result: Salesforce.\n4. **Critique**: Validated result.\n5. **Step 2**: Agent uses `search_tool('Salesforce CEO')`. Result: Marc Benioff.\n6. **Synthesis**: Agent combines facts to answer 'Marc Benioff'."),
        ("user", "What tech stack is good for this?"),
        ("assistant", "Popular frameworks include:\n- **LangChain**: Has 'LangGraph' specifically for building stateful, multi-actor agents.\n- **LlamaIndex**: Excellent data connectors and 'Agentic' query engines.\n- **AutoGen**: Good for multi-agent collaboration.\n- **DSPy**: For optimizing the prompts programmatically.\n\nFor the vector database, tools like Pinecone, Weaviate, or pgvector (Postgres) work well."),
        ("user", "Thanks, that helps!"),
        ("assistant", "You're welcome! Let me know if you want to dive deeper into any of those frameworks.")
    ]
    
    for role, content in turns:
        await message_repository.create(conversation['id'], role, content)
        
    print("Seeding complete!")
    print(f"\nLOGIN CREDENTIALS:\nEmail: {email}\nPassword: {password}")

if __name__ == "__main__":
    asyncio.run(seed())

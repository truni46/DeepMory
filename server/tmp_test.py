import asyncio
from modules.agents.memory.agentMemory import agentMemory
from config.database import db

async def test():
    await db.connect()
    userId = "test-user-12345"
    agentId = "test-agent"
    
    msgs = [
        {"role": "user", "content": "I am testing the new agentMemory system. I live in Hanoi."}
    ]
    print("Testing addMemory pipeline...")
    await agentMemory._processMemory(msgs, userId, agentId)
    
    print("\nTesting searchMemory...")
    res = await agentMemory.searchMemory(userId, "Where do I live?")
    print("Found:", res)
    
    await db.close()

if __name__ == '__main__':
    asyncio.run(test())

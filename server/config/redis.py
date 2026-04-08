import os
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

class RedisConfig:
    def __init__(self):
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.password = os.getenv('REDIS_PASSWORD', None)
        self.db = int(os.getenv('REDIS_DB', 0))
        self.redis_url = f"redis://:{self.password}@{self.host}:{self.port}/{self.db}" if self.password else f"redis://{self.host}:{self.port}/{self.db}"
redis_config = RedisConfig()

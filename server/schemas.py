from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

# Auth Schemas
class UserRegister(BaseModel):
    email: str
    password: str
    username: Optional[str] = None
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

# Project Schemas
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    config: Optional[Dict] = {}

# Conversation Schemas
class ConversationCreate(BaseModel):
    title: Optional[str] = None
    project_id: Optional[str] = None

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    project_id: Optional[str] = None

# Message Schemas
class MessageRequest(BaseModel):
    message: str
    conversationId: str
    projectId: Optional[str] = None

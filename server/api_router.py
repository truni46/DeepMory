from fastapi import APIRouter
from modules.auth.router import router as auth_router
from modules.projects.router import router as projects_router
from modules.conversations.router import router as conversations_router
from modules.chat.router import router as messages_router
from modules.settings.router import router as settings_router
from modules.knowledge.router import router as knowledge_router

router = APIRouter(prefix="/api")

router.include_router(auth_router)
router.include_router(projects_router)
router.include_router(conversations_router)
router.include_router(messages_router)
router.include_router(settings_router)
router.include_router(knowledge_router)

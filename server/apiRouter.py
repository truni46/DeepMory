from fastapi import APIRouter
from modules.auth.router import router as authRouter
from modules.projects.router import router as projectsRouter
from modules.conversations.router import router as conversationsRouter
from modules.message.router import router as messagesRouter
from modules.settings.router import router as settingsRouter
from modules.knowledge.router import router as knowledgeRouter
from modules.rag.router import router as ragRouter

router = APIRouter(prefix="/api")

router.include_router(authRouter)
router.include_router(projectsRouter)
router.include_router(conversationsRouter)
router.include_router(messagesRouter)
router.include_router(settingsRouter)
router.include_router(knowledgeRouter)
router.include_router(ragRouter)

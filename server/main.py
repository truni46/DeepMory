import os
from dotenv import load_dotenv

# MUST load environment variables FIRST, before importing any internal modules
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

import uvicorn
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from config.database import db
from config.logger import logger
from common.cacheService import cacheService
from apiRouter import router as apiRouter
from websocket.handlers import sio


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    logger.info("Starting AI Tutor Server...")
    
    # Connect to database
    await db.connect()
    
    # Connect to Redis
    await cacheService.connect()
    
    # Check database connection
    is_connected = await db.check_connection()
    if is_connected:
        logger.info("Using PostgreSQL database")
    else:
        logger.warning("Using JSON file storage (database not available)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down server...")
    await cacheService.close()
    await db.close()
    logger.info("Server stopped")


# Create FastAPI app
app = FastAPI(
    title="AI Tutor API",
    description="chatbot backend with SSE streaming and WebSocket support",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
frontendUrl = os.getenv('FRONTEND_URL', 'http://localhost:5173')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontendUrl, "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(apiRouter)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AI Tutor API",
        "version": "1.0.0",
        "framework": "FastAPI",
        "endpoints": {
            "health": "/api/health",
            "dbStatus": "/api/db-status",
            "conversations": "/api/conversations",
            "messages": "/api/messages",
            "chat": "/api/messages/chat/completions",
            "settings": "/api/settings"
        },
        "websocket": "/socket.io",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


# Create Socket.IO ASGI app
socketApp = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path='/socket.io'
)


# Run the server
if __name__ == "__main__":
    port = int(os.getenv('PORT', 3000))
    host = os.getenv('HOST', '0.0.0.0')
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Frontend URL: {frontendUrl}")
    logger.info(f"API Documentation: http://localhost:{port}/docs")
    
    uvicorn.run(
        socketApp,
        host=host,
        port=port,
        log_level="info"
    )

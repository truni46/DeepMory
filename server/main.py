import os
import uvicorn
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from config.database import db
from config.logger import logger
from common.cache_service import cache_service
from api_router import router as api_router
from websocket.handlers import sio

# Load environment variables (force load from server directory)
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    logger.info("Starting AI Tutor Server...")
    
    # Connect to database
    await db.connect()
    
    # Connect to Redis
    await cache_service.connect()
    
    # Check database connection
    is_connected = await db.check_connection()
    if is_connected:
        logger.info("Using PostgreSQL database")
    else:
        logger.warning("Using JSON file storage (database not available)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down server...")
    await cache_service.close()
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
frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:5173", "*"],  # Allow frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

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
            "messagesStream": "/api/messages/stream",
            "history": "/api/history/:conversationId",
            "settings": "/api/settings",
            "export": "/api/export/:conversationId"
        },
        "websocket": "/socket.io",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


# Create Socket.IO ASGI app
socket_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path='/socket.io'
)


# Run the server
if __name__ == "__main__":
    port = int(os.getenv('PORT', 3000))
    host = os.getenv('HOST', '0.0.0.0')
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Frontend URL: {frontend_url}")
    logger.info(f"API Documentation: http://localhost:{port}/docs")
    
    uvicorn.run(
        socket_app,
        host=host,
        port=port,
        log_level="info"
    )

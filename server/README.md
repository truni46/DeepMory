# AI Tutor - Python Backend

Python backend for AI Tutor chatbot application using FastAPI.

## Features

- 🚀 **FastAPI Framework** - High-performance async web framework
- 🔄 **SSE Streaming** - Server-Sent Events for real-time message streaming
- 🔌 **WebSocket Support** - Real-time bidirectional communication
- 💾 **PostgreSQL Integration** - Primary database with JSON fallback
- 📊 **Comprehensive Logging** - Multi-file logging system
- 📚 **Auto-generated API Docs** - Swagger UI and ReDoc

## Quick Start

### 1. Install Dependencies

```bash
cd server_python
pip install -r requirements.txt
```

### 2. Configure Environment

The `.env` file is already configured. Modify if needed:

```env
PORT=3000
USE_DATABASE=true
DB_NAME=ai_tutor_db
DB_USER=ai_tutor
DB_PASSWORD=secure_password_123
```

### 3. Run Database Migration (if using PostgreSQL)

```bash
python migrations/migrate.py
```

### 4. Start the Server

```bash
# Option 1: Using Python directly
python main.py

# Option 2: Using Uvicorn
uvicorn main:socket_app --host 0.0.0.0 --port 3000 --reload
```

Server will start on `http://localhost:3000`

## API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:3000/docs
- **ReDoc**: http://localhost:3000/redoc

## Project Structure

```
server_python/
├── config/
│   ├── database.py      # Database connection & queries
│   └── logger.py        # Logging configuration
├── routes/
│   └── api.py           # API endpoints
├── services/
│   ├── message_service.py      # Message processing
│   ├── conversation_service.py # Conversation management
│   ├── history_service.py      # Chat history
│   ├── settings_service.py     # Settings management
│   └── export_service.py       # Export functionality
├── websocket/
│   └── handlers.py      # WebSocket event handlers
├── migrations/
│   └── migrate.py       # Database migration script
├── main.py              # Application entry point
├── requirements.txt     # Python dependencies
└── .env                 # Environment variables
```

## API Endpoints

All endpoints maintain compatibility with the Node.js version:

- **Health**: `GET /api/health`
- **Database Status**: `GET /api/db-status`
- **Conversations**: `GET|POST|PUT|DELETE /api/conversations`
- **Messages**: `POST /api/messages` (non-streaming)
- **Streaming**: `POST /api/messages/stream` (SSE)
- **History**: `GET /api/history/:conversationId`
- **Search**: `POST /api/history/search`
- **Settings**: `GET|PUT /api/settings`
- **Export**: `GET /api/export/:conversationId?format=json|txt|md`

## WebSocket Events

- **connect** - Client connection established
- **disconnect** - Client disconnected
- **sendMessage** - Send message (non-streaming)
- **sendMessageStreaming** - Send message with streaming
- **typing** - User typing indicator

## Development

### Enable Auto-reload

```bash
uvicorn main:socket_app --reload
```

### View Logs

Logs are stored in `logs/` directory:
- `combined.log` - All logs
- `error.log` - Errors only
- `chat.log` - Chat messages
- `api.log` - API requests

## Differences from Node.js Version

The Python backend maintains full API compatibility. Key implementation differences:

- **Framework**: FastAPI instead of Express
- **Async**: Native Python async/await
- **WebSocket**: python-socketio instead of Socket.IO
- **Database**: asyncpg instead of pg
- **Logging**: Python logging instead of Winston

## Integration with Frontend

The React frontend works with zero changes. Just ensure:

1. Python backend runs on `http://localhost:3000`
2. Frontend `.env` points to `http://localhost:3000`

That's it! The frontend will automatically connect to the Python backend.

## Production Deployment

For production, use a proper ASGI server:

```bash
gunicorn main:socket_app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:3000
```

## License

ISC

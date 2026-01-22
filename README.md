# AI Tutor

A modern, feature-rich chatbot application, supporting both Server-Sent Events (SSE) streaming and WebSocket communication.

![Version](https://img.shields.io/badge/version-1.0.0-green)
![License](https://img.shields.io/badge/license-ISC-blue)

## ✨ Features

- 🔄 **Dual Communication Modes**:
  - **SSE Streaming** (Default) - Real-time streaming responses like ChatGPT
  - **WebSocket** - Bidirectional real-time communication with Socket.IO
- 💬 **Full Conversation Management** - Create, view, delete conversations
- 💾 **Persistent Chat History** - PostgreSQL database with JSON fallback
- 📊 **Comprehensive Logging** - Multi-file logging system
- 🔍 **Full-Text Search** - Search through chat history
- 📤 **Export Conversations** - Export as JSON, TXT, or Markdown
- ⚙️ **Customizable Settings** - Communication mode, timestamps, themes
- 📱 **Responsive Design** - Works on desktop, tablet, and mobile

## 🚀 Quick Start

### Prerequisites

- **Python** (v3.8 or higher)
- **Node.js** (v16 or higher) - for frontend only
- **PostgreSQL** (v12 or higher) - Optional but recommended

### Installation

1. **Clone the repository** (or navigate to the project directory)

```bash
cd d:/Work/VTC_Telecom/AI_Tutor/ai-tutor-web
```

2. **Install Backend Dependencies**

```bash
cd server
pip install -r requirements.txt
```

3. **Install Frontend Dependencies**

```bash
cd ..
npm install
```

4. **Configure Environment Variables**

**Backend** (`server/.env`):
```env
PORT=3000
HOST=0.0.0.0
NODE_ENV=development

# Database (optional - uses JSON files if disabled)
USE_DATABASE=false
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ai_tutor_db
DB_USER=ai_tutor
DB_PASSWORD=your_password

FRONTEND_URL=http://localhost:5173
```

**Frontend** (`.env`):
```env
VITE_API_URL=http://localhost:3000/api
VITE_SOCKET_URL=http://localhost:3000
```

### Running the Application

1. **Start Backend Server**

```bash
cd server
python main.py
```

Server will start on `http://localhost:3000`

2. **Start Frontend** (in a new terminal)

```bash
npm run dev
```

Frontend will start on `http://localhost:5173`

3. **Open in Browser**

Navigate to `http://localhost:5173`

## 🗄️ Database Setup (Optional)

### Install PostgreSQL

**Windows**: Download from [postgresql.org](https://www.postgresql.org/download/windows/)

### Create Database

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create database and user
CREATE DATABASE ai_tutor_db;
CREATE USER ai_tutor WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE ai_tutor_db TO ai_tutor;
```

### Run Migrations

```bash
cd server
python migrations/migrate.py
```

### Update .env

```env
USE_DATABASE=true
DB_PASSWORD=your_password
```

## 📡 API Endpoints

### Health & Status
- `GET /api/health` - Health check
- `GET /api/db-status` - Database connection status

### Conversations
- `GET /api/conversations` - List all conversations
- `POST /api/conversations` - Create new conversation
- `GET /api/conversations/:id` - Get conversation details
- `PUT /api/conversations/:id` - Update conversation
- `DELETE /api/conversations/:id` - Delete conversation

### Messages
- `POST /api/messages` - Send message (non-streaming)
- `POST /api/messages/stream` - Send message (SSE streaming)

### History
- `GET /api/history/:conversationId` - Get chat history
- `POST /api/history/search` - Search messages

### Settings
- `GET /api/settings` - Get settings
- `PUT /api/settings` - Update settings

### Export
- `GET /api/export/:conversationId?format=json` - Export conversation

## 🧪 Testing with Postman

1. Import the API collection or test manually:

```
POST http://localhost:3000/api/conversations
Content-Type: application/json

{
  "title": "Test Chat"
}
```

2. Send a message:

```
POST http://localhost:3000/api/messages/stream
Content-Type: application/json

{
  "message": "Hello, AI!",
  "conversationId": "<conversation-id>"
}
```

## 🎨 Customization

### Change Theme Colors

Edit `tailwind.config.js`:

```javascript
colors: {
  'deep-forest': '#0d3d2f',  // Change these values
  'emerald': '#1a5d45',
  'bright-green': '#22c55e',
  // ...
}
```

### Integrate Real AI

Edit `server/services/message_service.py` and replace the `generate_ai_response` function with your AI API:

```python
# Example: OpenAI Integration
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="your-api-key")

async def generate_ai_response(message, conversation_history):
    response = await client.chat.completions.create(
        model="gpt-4",
        messages=conversation_history
    )
    return response.choices[0].message.content
```

## 📂 Project Structure

```
ai-tutor-web/
├── server/                    # Backend (Python + FastAPI)
│   ├── config/               # Configuration
│   ├── routes/               # API routes
│   ├── services/             # Business logic
│   ├── websocket/            # WebSocket handlers
│   ├── migrations/           # Database migrations
│   └── main.py               # Application entry
├── src/                      # Frontend (React + Vite)
│   ├── components/           # React components
│   ├── services/             # API & WebSocket clients
│   └── utils/                # Utility functions
└── README.md
```

## 🛠️ Tech Stack

**Frontend:**
- React 18 + Vite
- Tailwind CSS
- Socket.IO Client

**Backend:**
- Python + FastAPI
- Socket.IO (python-socketio)
- PostgreSQL (psycopg2)
- Python logging

## 📝 Logs

Backend logs are stored in `server/logs/`:
- `combined.log` - All logs
- `error.log` - Errors only
- `chat.log` - Chat messages
- `api.log` - API requests

## 🔧 Troubleshooting

### Backend won't start
- Check if port 3000 is available
- Verify Node.js version: `node --version`
- Check database connection if using PostgreSQL

### Frontend won't connect
- Ensure backend is running
- Check `.env` file has correct URLs
- Clear browser cache

### Database errors
- Verify PostgreSQL is running
- Check connection credentials in `.env`
- Run migrations: `npm run migrate`

## 🤝 Contributing

Feel free to customize and extend this chatbot for your needs!

## 📄 License

ISC License - See LICENSE file for details

## 🙋 Support

For issues or questions about this implementation, refer to the documentation files in the `brain` directory.

---

**Built with ❤️ using React, Node.js, and PostgreSQL**
# AI Tutor

A modern, feature-rich chatbot application with a modular Python backend and React frontend.

![Version](https://img.shields.io/badge/version-1.1.0-green)
![License](https://img.shields.io/badge/license-ISC-blue)

## ✨ Features

- 🧠 **Modular Architecture** - Domain-driven backend design (`auth`, `chat`, `llm`, etc.)
- 🔄 **Real-time Communication** - Supports both **SSE Streaming** and **WebSocket**.
- 🤖 **LLM Integration** - Support for Ollama, OpenAI, Gemini, vLLM via provider pattern.
- 💾 **Persistence** - PostgreSQL with JSON fallback (stored in `/data`).
- 📂 **Project Management** - Organize chats into projects with document context (RAG).
- 🛠️ **MCP Support** - Extensible via Model Context Protocol.

## 🚀 Quick Start

### Prerequisites

- **Python** (v3.10+)
- **Node.js** (v18+)
- **PostgreSQL** (Optional, falls back to JSON)
- **Redis** (Optional, for caching)

### Installation

1. **Clone the repository**
   ```bash
   cd d:/Work/VTC_Telecom/AI_Tutor/ai-tutor-web
   ```

2. **Backend Setup**
   ```bash
   cd server
   python -m venv .venv
   # Activate: .venv\Scripts\Activate (Windows) or source .venv/bin/activate (Linux/Mac)
   pip install -r requirements.txt
   ```

3. **Frontend Setup**
   ```bash
   cd ..
   npm install
   ```

### Configuration

**Backend** (`server/.env`):
```env
PORT=3000
HOST=0.0.0.0
FRONTEND_URL=http://localhost:5173

# Database
USE_DATABASE=true # Set false to use JSON files in /data
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ai_tutor_db
DB_USER=ai_tutor
DB_PASSWORD=your_password

# LLM Config
LLM_PROVIDER=ollama
LLM_MODEL=mistral
OLLAMA_BASE_URL=http://localhost:11434/v1
```

**Frontend** (`.env`):
```env
VITE_API_URL=http://localhost:3000/api
VITE_SOCKET_URL=http://localhost:3000
```

### Running the Application

**Terminal 1: Backend**
```bash
cd server
# Ensure venv is activated
python main.py
```
*Server runs on `http://localhost:3000`*

**Terminal 2: Frontend**
```bash
# In project root
npm run dev
```
*Frontend runs on `http://localhost:5173`*

## 📂 Project Structure

```
ai-tutor-web/
├── server/
│   ├── modules/              # Feature modules
│   │   ├── auth/             # Authentication
│   │   ├── conversations/    # Chat management
│   │   ├── messages/         # Message logic
│   │   ├── llm/              # LLM Providers
│   │   ├── mcp/              # MCP Providers
│   │   └── ...
│   ├── common/               # Shared utilities
│   ├── config/               # Configuration
│   ├── testing/              # Verification scripts
│   ├── api_router.py         # Main router
│   └── main.py               # Entry point
├── src/                      # React Frontend
├── data/                     # Data storage (JSON/Uploads)
└── README.md
```

## 🧪 Testing

Run verification scripts to ensure everything is working:

```bash
python server/testing/verifyServices.py
python server/testing/verify_api.py
```
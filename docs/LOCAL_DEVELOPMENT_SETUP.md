# Local Development Setup Guide

Step-by-step instructions to configure, run, and develop the Legal RAG Property Intelligence Platform locally.

## 1. Prerequisites

- **Python**: 3.10+ (recommended: 3.11)
- **Node.js**: 18.0+ and npm / pnpm
- **PostgreSQL**: 15+ with the `pgvector` extension enabled
- **Git**

---

## 2. Backend Setup

1. **Navigate to backend**:
   ```bash
   cd backend
   ```
2. **Create and activate a virtual environment**:
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Configuration**:
   Copy `.env.example` to `.env` and fill in:
   - `DATABASE_URL`: `postgresql+asyncpg://user:pass@localhost:5432/legal_rag`
   - `GROQ_API_KEY`: Your Groq API key
5. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```
6. **Start the FastAPI backend**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   API docs will be available at `http://localhost:8000/docs`.

---

## 3. Frontend Setup

1. **Navigate to frontend**:
   ```bash
   cd frontend
   ```
2. **Install node dependencies**:
   ```bash
   npm install
   ```
3. **Start the Vite development server**:
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.

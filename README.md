# Ollama Console (Local Django Dashboard)

This project is a **local-only** Django dashboard for managing **Ollama** on your Linux machine and chatting with local models.

## Features
- **Status**: shows Ollama base URL + version
- **Models**: list local models, **pull** a model (with live progress), **delete** a model
- **Running models**: list models currently loaded in memory
- **Chat**: streaming responses, model selector, and **saved chat history** (SQLite)

## Requirements
- Python (recommended: 3.11+)
- Ollama installed and running locally

## Setup
From the project root:

```bash
cd /home/siavash-rahimi/Desktop/projects/ollama
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
python manage.py migrate
```

## Run
Make sure Ollama is running (for example):

```bash
ollama serve
```

Then run Django:

```bash
cd /home/siavash-rahimi/Desktop/projects/ollama
source env/bin/activate
python manage.py runserver 127.0.0.1:8000
```

Open the UI at `http://127.0.0.1:8000/`.

## Configuration
Edit `[ollama_dashboard/settings.py](ollama_dashboard/settings.py)`:
- `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- `OLLAMA_REQUEST_TIMEOUT_SECONDS` (default: `60`)

## Troubleshooting
- If the UI shows **“Ollama is not reachable”**:
  - Verify Ollama is running: `ollama serve`
  - Verify the API responds:

```bash
curl http://localhost:11434/api/version
```

## Project notes
- **Templates**: `console/templates/console/`
- **Static files** (CSS/JS + vendored HTMX): `assets/`
- **Ollama client wrapper**: `console/services/ollama.py`
- **Streaming endpoints**:
  - `POST /api/models/pull` (NDJSON stream)
  - `POST /api/chat/stream` (NDJSON stream)


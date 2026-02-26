# Ollama Console (Local Django Dashboard)

This project is a **local-only** Django dashboard for managing **Ollama** on your Linux machine, chatting with local models, and **fine-tuning models**.

## Features
- **Status**: shows Ollama base URL + version
- **Models**: list local models, **pull** a model (with live progress), **delete** a model
- **Running models**: list models currently loaded in memory
- **Chat**: streaming responses, model selector, and **saved chat history** (SQLite)
- **Fine-tuning**: create and manage fine-tuned models using Modelfiles and training data

## Requirements
- Python (recommended: 3.11+)
- Ollama installed and running locally
- Sufficient disk space for model files and training data
- Adequate RAM/VRAM for model fine-tuning operations

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
Edit `ollama_dashboard/settings.py`:
- `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- `OLLAMA_REQUEST_TIMEOUT_SECONDS` (default: `60`)
- `OLLAMA_MODEL_STORAGE_PATH` (optional: custom path for model storage)

## Fine-tuning Features

### Available Fine-tuning Capabilities
1. **Model Creation**: Create new models from base models with custom parameters
2. **Modelfile Management**: Create, edit, and apply Modelfiles for model configuration
3. **Training Data Preparation**: Upload and format training data for fine-tuning
4. **Fine-tuning Jobs**: Monitor fine-tuning progress and manage training sessions
5. **Model Versioning**: Keep track of different versions of fine-tuned models

### Using Fine-tuning
1. **Prepare Training Data**:
   - Format your data in JSONL or text format
   - Ensure proper prompt-completion pairs for instruction tuning
   - Upload through the web interface or place in the designated data directory

2. **Create Modelfile**:
   - Start from a base model (e.g., `llama3.2:3b`)
   - Configure training parameters (epochs, learning rate, etc.)
   - Specify system prompts and templates

3. **Start Fine-tuning**:
   - Select base model and training data
   - Configure hyperparameters
   - Monitor progress through the dashboard
   - Save fine-tuned model with custom name

### Example Fine-tuning Workflow
```bash
# Using the dashboard interface:
1. Navigate to "Fine-tuning" section
2. Select base model (e.g., llama3.2:3b)
3. Upload training data
4. Configure parameters:
   - Epochs: 3
   - Learning rate: 0.0001
   - Batch size: 4
5. Start fine-tuning job
6. Monitor progress in real-time
7. Test fine-tuned model in chat interface
```

## Project Structure
- **Templates**: `console/templates/console/`
- **Static files** (CSS/JS + vendored HTMX): `assets/`
- **Ollama client wrapper**: `console/services/ollama.py`
- **Fine-tuning utilities**: `console/services/finetune.py`
- **Streaming endpoints**:
  - `POST /api/models/pull` (NDJSON stream)
  - `POST /api/chat/stream` (NDJSON stream)
  - `POST /api/finetune/stream` (NDJSON stream for fine-tuning progress)

## Troubleshooting
- If the UI shows **"Ollama is not reachable"**:
  - Verify Ollama is running: `ollama serve`
  - Verify the API responds:

```bash
curl http://localhost:11434/api/version
```

- If **fine-tuning fails**:
  - Check available disk space
  - Verify training data format
  - Ensure base model is properly downloaded
  - Check system resources (RAM/VRAM)

- If **models don't appear**:
  - Check Ollama model list: `ollama list`
  - Verify model storage permissions
  - Restart Ollama service if needed

## Performance Notes
- Fine-tuning requires significant system resources
- Larger models need more VRAM/RAM
- Consider using quantization for memory-constrained systems
- Training progress is saved periodically; interrupted jobs can often be resumed

## Advanced Usage
### Command-line Fine-tuning
For advanced users, fine-tuning can also be performed via command line:

```bash
# Create a Modelfile
cat > MyModelfile << EOF
FROM llama3.2:3b
PARAMETER num_epoch 3
PARAMETER learning_rate 0.0001
SYSTEM "You are a helpful assistant specialized in coding."
EOF

# Create and run the model
ollama create my-tuned-model -f MyModelfile
ollama run my-tuned-model
```

### Batch Processing
The dashboard supports batch fine-tuning jobs for multiple datasets or parameter combinations.

## Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License
[Add your license information here]

## Support
For issues and feature requests, please use the project's issue tracker.
# Workers

Background job workers using Cloud Tasks and Cloud Run

## Structure
```
workers/
├── tasks/          # Task definitions
│   ├── base.py     # Base task class
│   └── hello_world.py
├── services/       # Business logic
│   └── task_manager.py
├── api/           # API routes
│   └── routes.py
├── tests/         # Unit tests
│   └── utils/     # Utility tests
└── main.py       # FastAPI application
```

## Setup

1. Copy `.env.example` to `.env` and update the values:
   ```bash
   cp .env.example .env
   ```

2. Create virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # Install development dependencies for testing
   ```

3. Run locally:
   ```bash
   uvicorn main:app --reload
   ```

4. Build using Docker
   ```bash
   docker build -t userport-workers-dev .
   ```

5. Run built Docker container
   ```bash
   docker run -p 8080:8080 --env-file .env \
   -v $(pwd):/app \
   -v $(pwd)/secrets/service-account.json:/secrets/service-account.json \
   userport-workers-dev
  ```

## Usage

1. Create a task:
   ```bash
   curl -X POST http://localhost:8080/api/v1/tasks/create/hello_world \
        -H "Content-Type: application/json" \
        -d '{"message": "Hello from task!"}'
   ```

2. Tasks will be executed automatically via Cloud Tasks calling the worker endpoints

## Testing

Run the unit tests with pytest:

```bash
# Activate your virtual environment first
source venv/bin/activate

# Run all tests
python -m pytest

# Run specific tests
python -m pytest tests/utils/test_retry_utils.py

# Run tests with verbose output
python -m pytest -v

# Run tests with code coverage report
python -m pytest --cov=workers
```

## Deployment

```bash
# Create Cloud Tasks queue
gcloud tasks queues create hello-world-queue \
    --location=us-central1

# Deploy to Cloud Run
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/workers
gcloud run deploy workers \
    --image gcr.io/YOUR_PROJECT_ID/workers \
    --platform managed \
    --region us-central1
```

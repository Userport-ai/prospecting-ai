# Userport Workers

A collection of background workers for enriching account and lead data, leveraging various data sources and AI services.

## Features

### Account Enrichment
- **Company Information**: Basic company details, funding, and industry data
- **Technology Stack**: Website technology detection using BuiltWith
- **Recent Developments**: Company updates and news

### Lead Generation & Research
- **Apollo Integration**: Find potential leads using Apollo API
- **LinkedIn Research**: Analyze lead activities and engagement
- **ProxyCurl Integration**: Enrich lead data with detailed profiles

### AI-Powered Analysis
- **Lead Scoring**: Evaluate leads based on fit and engagement
- **Personality Insights**: Generate lead personality profiles
- **Custom Column Generation**: AI-generated custom field values

## Getting Started

### Prerequisites
- Python 3.11+
- Google Cloud account with required services enabled
- API keys for external services

### Environment Variables
```bash
# Core Configuration
ENVIRONMENT=development
LOG_LEVEL=DEBUG
GOOGLE_CLOUD_PROJECT=your-project-id
BIGQUERY_DATASET=userport_enrichment

# API Keys
APOLLO_API_KEY=your-apollo-key
PROXYCURL_API_KEY=your-proxycurl-key
BUILTWITH_API_KEY=your-builtwith-key
OPENAI_API_KEY=your-openai-key

# Service Configuration
DJANGO_CALLBACK_URL=http://localhost:8000/api/v2/internal/enrichment-callback
```

### Installation

1. Clone the repository:
```bash
git clone https://github.com/your-org/prospecting-ai.git
cd prospecting-ai/workers
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the service:
```bash
uvicorn main:app --reload
```

## Usage

### Account Technology Enrichment

Fetch and analyze technology stack data for an account:

```python
# Using the API
response = requests.post(
    "api/v1/tasks/create/technology_enrichment_builtwith",
    json={
        "account_id": "account-uuid",
        "account_data": {
            "website": "https://example.com"
        }
    }
)

# Check status
job_id = response.json()["job_id"]
status = requests.get(f"api/v1/tasks/{job_id}/status")
```

See [Technology Enrichment Documentation](docs/technology-enrichment.md) for detailed usage.

### Lead Generation

Generate potential leads for an account:

```python
response = requests.post(
    "api/v1/tasks/create/generate_leads_apollo",
    json={
        "account_id": "account-uuid",
        "account_data": {
            "website": "https://example.com"
        },
        "product_data": {
            "description": "Product description",
            "persona_role_titles": ["CTO", "VP Engineering"]
        }
    }
)
```

### Lead Research

Analyze LinkedIn activities for a lead:

```python
response = requests.post(
    "api/v1/tasks/create/lead_linkedin_research",
    json={
        "lead_id": "lead-uuid",
        "account_id": "account-uuid",
        "linkedin_url": "https://linkedin.com/in/username"
    }
)
```

## Architecture

### Components
- FastAPI web application
- Google Cloud Tasks for job queuing
- BigQuery for data storage
- Cloud Run for serverless deployment

### Data Flow
1. API receives enrichment request
2. Task is created in Cloud Tasks
3. Worker processes task asynchronously
4. Results stored in BigQuery
5. Callback sent to Django application

## Development

### Running Tests
```bash
# Run all tests
pytest

# Run specific test category
pytest tests/services/
pytest tests/tasks/
pytest tests/integration/

# Run with coverage
pytest --cov=.
```

### Adding New Features

1. Create new task class inheriting from `BaseTask`
2. Implement required methods:
   - `create_task_payload`
   - `execute`
3. Add to task registry in `api/routes.py`
4. Add tests and documentation

## Monitoring

### Metrics
- Task success/failure rates
- Processing times
- API call statistics
- Data quality scores

### Logging
- Structured JSON logs
- Request/response tracking
- Error details with stack traces

## Support

For issues and questions:
1. Check documentation in `docs/`
2. Review existing issues
3. Contact development team

## Acknowledgments

- Built with FastAPI
- Powered by Google Cloud
- Uses various third-party APIs and services

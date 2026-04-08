# WikiTree Intelligence API

FastAPI backend service for the WikiTree Intelligence genealogy workbench.

## Overview

The API provides:

- **Google OAuth authentication** with session management
- **WikiTree API integration** for profile search and data retrieval
- **Health and status endpoints** for monitoring
- **CORS configuration** for local and production frontends
- **Async-first design** with proper async/await patterns

## Tech Stack

- **Python 3.12** with type hints
- **FastAPI** for async HTTP endpoints
- **Pydantic** for data validation and settings
- **Gunicorn + Uvicorn** for production ASGI serving
- **Pytest** for unit and integration testing
- **Ruff** for linting and formatting
- **Pyrefly** for static type checking

## Project Structure

```
apps/api/
├── src/
│   └── api/
│       ├── routes/          # API route handlers
│       ├── models/          # Pydantic models
│       ├── security/        # Auth and security
│       ├── utils/           # Helper functions
│       ├── app.py           # FastAPI application
│       ├── enums.py         # Application enums
│       └── settings.py      # Configuration
├── tests/
│   ├── conftest.py          # Shared fixtures
│   └── test_*.py            # Test modules
├── pyproject.toml           # Dependencies and config
├── Dockerfile               # Production container
└── entrypoint.sh            # Container entrypoint
```

## Local Development

### Prerequisites

- Python 3.12+
- Google OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)

### Setup

1. **Create virtual environment:**

   ```bash
   cd apps/api
   python3.12 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**

   ```bash
   pip install -e ".[dev]"
   ```

3. **Configure environment:**

   ```bash
   cp .env.example .env.local
   ```

   Edit `.env.local` with your settings:

   ```bash
   # Required
   GOOGLE_OAUTH_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
   SESSION_SECRET_KEY=generate-with-openssl-rand-hex-32

   # Optional
   LOG_LEVEL=INFO
   PORT=8080
   AUTH_DISABLED=false
   CLIENT_ORIGINS=["http://localhost:5173","http://localhost:3000"]
   ```

4. **Run the development server:**

   ```bash
   uvicorn api.app:app --reload --env-file=.env.local
   ```

   API available at: http://localhost:8080

   Interactive docs: http://localhost:8080/docs

### Docker Development

Run the full stack (API + UI + PostgreSQL):

```bash
# From repository root
docker-compose up --build
```

API available at: http://localhost:8080

## Testing

### Run all tests:

```bash
pytest -v
```

### Run with coverage:

```bash
pytest --cov=api --cov-report=term-missing
```

### Run specific test file:

```bash
pytest tests/test_health.py -v
```

### Run tests in watch mode:

```bash
pytest -v --cov=api -x
```

## Code Quality

### Type checking:

```bash
pyrefly check src/
```

### Linting:

```bash
ruff check src/
```

### Formatting:

```bash
# Format code
ruff format src/

# Check formatting without changes
ruff format --check src/
```

### Run all checks:

```bash
# Before committing
ruff check src/
ruff format src/
ruff format --check src/
pyrefly check src/
pytest -v
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_OAUTH_CLIENT_ID` | Yes | - | Google OAuth client ID |
| `SESSION_SECRET_KEY` | Yes | - | Secret key for session signing |
| `PORT` | No | `8080` | Server port |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `ENVIRONMENT` | No | `development` | Environment name |
| `AUTH_DISABLED` | No | `false` | Disable authentication (dev only) |
| `CLIENT_ORIGINS` | No | `["http://localhost:5173"]` | Allowed CORS origins (JSON array) |
| `ALLOWED_HOSTED_DOMAINS` | No | `[]` | Restrict to Google Workspace domains (JSON array) |

## API Endpoints

### Health Check

- `GET /health` - Server health status

### Authentication

- `GET /auth/google/url` - Get Google OAuth URL
- `GET /auth/google/callback` - OAuth callback handler
- `GET /auth/me` - Get current user
- `POST /auth/logout` - Logout current user

## Development Guidelines

See [`CLAUDE.md`](../../CLAUDE.md) for comprehensive development guidelines including:

- FastAPI endpoint patterns
- Pydantic model best practices
- Type hint standards
- Testing requirements
- Code style and formatting
- Common patterns

## Production Deployment

The API uses a multi-stage Docker build with:

- Non-root user for security
- Gunicorn + Uvicorn workers for concurrency
- Health check endpoint
- Optimized Python dependencies

Environment variables are passed through docker-compose or container orchestration.

## Contributing

1. Follow the development guidelines in [`CLAUDE.md`](../../CLAUDE.md)
2. Ensure all tests pass: `pytest -v`
3. Ensure code quality checks pass: `ruff check` + `ruff format --check` + `pyrefly check`
4. Keep PRs focused and under 10 files when possible
5. Maintain or improve code coverage (target: 80%+)

## License

Apache 2.0 - See [LICENSE](../../LICENSE) for details.

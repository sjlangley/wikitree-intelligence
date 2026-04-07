# CLAUDE.md

Development instructions and guidelines for the WikiTree Intelligence project.

## Project Overview

WikiTree Intelligence is a local-first genealogy workbench for reconciling GEDCOM data with WikiTree. The project emphasizes clean architecture, comprehensive testing, and maintainable code.

## Tech Stack

### Frontend (`apps/ui/`)

- **React 19** with TypeScript
- **Vite 8** for build tooling
- **React Compiler** (babel-plugin-react-compiler) — automatic optimization
- **Vitest** for unit/component testing
- **React Testing Library** for component testing
- **ESLint** + **Prettier** for code quality
- **TypeScript 6** with strict type checking

### Backend (`apps/api/`)

- **Python 3.12** with type hints
- **FastAPI** for async HTTP endpoints
- **Pydantic** for data validation and settings
- **Pytest** for unit and integration testing
- **Ruff** for linting and formatting
- **Pyrefly** for static type checking
- **Gunicorn + Uvicorn** for production deployment

### E2E Testing

- Playwright in `e2e/` directory
- Critical user flows must have E2E coverage

## UI Development Guidelines

### File Organization

```
apps/ui/
├── src/
│   ├── components/      # Reusable React components
│   ├── pages/          # Top-level page components
│   ├── hooks/          # Custom React hooks
│   ├── utils/          # Pure utility functions
│   ├── types/          # TypeScript type definitions
│   ├── assets/         # Images, icons, fonts
│   ├── App.tsx         # Root app component
│   └── main.tsx        # Application entry point
└── tests/
    ├── setup.ts        # Test environment configuration
    └── *.test.tsx      # Component and hook tests
```

### React Component Guidelines

#### 1. Component Structure

**Always use function components** with TypeScript:

```tsx
import { useState } from "react";

interface PersonCardProps {
  name: string;
  birthYear?: number;
  onSelect: (id: string) => void;
}

export function PersonCard({ name, birthYear, onSelect }: PersonCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="person-card">
      <h3>{name}</h3>
      {birthYear && <span>Born: {birthYear}</span>}
      <button onClick={() => onSelect(name)}>Select</button>
    </div>
  );
}
```

**Key principles:**

- Use named exports for components (not default exports)
- Define explicit TypeScript interfaces for props
- Mark optional props with `?`
- Place component logic before JSX return
- Keep components focused on a single responsibility

#### 2. React Compiler Optimization

This project uses the **React Compiler** which automatically optimizes components. Follow these rules to ensure the compiler works effectively:

**✅ DO:**

- Write clean, straightforward React code
- Use standard React patterns (useState, useEffect, etc.)
- Keep side effects in useEffect hooks
- Use proper dependency arrays

**❌ DON'T:**

- Manually memoize with `useMemo`/`useCallback` unless profiling shows need
- Mutate props or state directly
- Use ref manipulation for state updates
- Create complex closure dependencies

**Example - Let React Compiler handle optimization:**

```tsx
// ✅ GOOD - React Compiler optimizes automatically
export function UserList({ users }: { users: User[] }) {
  const sortedUsers = users.sort((a, b) => a.name.localeCompare(b.name));

  return (
    <ul>
      {sortedUsers.map(user => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}

// ❌ BAD - Unnecessary manual memoization
export function UserList({ users }: { users: User[] }) {
  const sortedUsers = useMemo(
    () => users.sort((a, b) => a.name.localeCompare(b.name)),
    [users]
  );

  return (
    <ul>
      {sortedUsers.map(user => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}
```

#### 3. State Management

**Use local state for UI concerns:**

```tsx
const [isOpen, setIsOpen] = useState(false);
const [searchQuery, setSearchQuery] = useState("");
```

**Use props for data flow:**

```tsx
interface Props {
  person: Person;
  onUpdate: (person: Person) => void;
}
```

**Keep state close to where it's used** — avoid lifting state unnecessarily.

#### 4. Event Handlers

**Name handlers with `handle` prefix:**

```tsx
function handleSubmit(event: React.FormEvent) {
  event.preventDefault();
  // ...
}

function handlePersonClick(personId: string) {
  // ...
}
```

**For callbacks passed as props, use `on` prefix:**

```tsx
interface Props {
  onSave: (data: FormData) => void;
  onCancel: () => void;
}
```

#### 5. TypeScript Best Practices

**Always type component props:**

```tsx
interface ButtonProps {
  variant: "primary" | "secondary" | "danger";
  size?: "small" | "medium" | "large";
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}
```

**Use type inference for state:**

```tsx
// ✅ Type automatically inferred as boolean
const [isLoading, setIsLoading] = useState(false);

// ✅ Explicit typing when needed
const [data, setData] = useState<Person | null>(null);
```

**Avoid `any`** — use `unknown` or proper types:

```tsx
// ❌ BAD
function processData(data: any) { ... }

// ✅ GOOD
function processData(data: unknown) {
  if (typeof data === "object" && data !== null) {
    // Type guard
  }
}
```

### Testing Requirements

#### Every component must have tests

Create test files alongside components or in `tests/` directory:

```
PersonCard.tsx
PersonCard.test.tsx
```

#### Test Structure

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PersonCard } from "./PersonCard";

describe("PersonCard", () => {
  it("renders person name", () => {
    render(<PersonCard name="John Doe" onSelect={() => {}} />);

    const heading = screen.getByRole("heading", { name: /john doe/i });
    expect(heading).toBeInTheDocument();
  });

  it("displays birth year when provided", () => {
    render(<PersonCard name="Jane Smith" birthYear={1950} onSelect={() => {}} />);

    expect(screen.getByText(/born: 1950/i)).toBeInTheDocument();
  });

  it("calls onSelect when button clicked", async () => {
    const handleSelect = vi.fn();
    const { user } = render(
      <PersonCard name="Test Person" onSelect={handleSelect} />
    );

    await user.click(screen.getByRole("button", { name: /select/i }));
    expect(handleSelect).toHaveBeenCalledWith("Test Person");
  });
});
```

#### Testing Guidelines

**Focus on user behavior:**

- Query elements by role, label, or text (not test IDs)
- Test what users see and interact with
- Avoid implementation details

**Cover critical paths:**

- Happy path rendering
- User interactions (clicks, form submissions)
- Conditional rendering
- Error states

**Use React Testing Library queries:**

```tsx
// ✅ Preferred queries (in order)
screen.getByRole("button", { name: /submit/i })
screen.getByLabelText(/email/i)
screen.getByText(/loading/i)

// ❌ Avoid
screen.getByTestId("submit-button")
```

### Code Quality Standards

#### Running Quality Checks

```bash
cd apps/ui

# Type checking
npm run build  # Runs tsc -b

# Linting
npm run lint       # Check for issues
npm run lint:fix   # Auto-fix issues

# Formatting
npm run format       # Format code
npm run format:check # Check formatting

# Testing
npm run test         # Run all tests
npm run test:watch   # Watch mode
npm run test:ui      # UI mode with coverage
npm run test:ci      # CI mode with coverage
```

#### Code Style

**Follow the ESLint configuration:**

- Modern ESLint flat config
- React Hooks rules enforced
- React Refresh compatibility
- TypeScript strict mode

**Prettier handles formatting** — don't argue about styles:

- 2-space indentation
- No semicolons (unless required)
- Double quotes for strings
- Trailing commas where valid

#### Import Organization

```tsx
// 1. React imports
import { useState, useEffect } from "react";

// 2. Third-party imports
import { formatDate } from "date-fns";

// 3. Local imports - types
import type { Person } from "../types/person";

// 4. Local imports - components/hooks/utils
import { PersonCard } from "./PersonCard";
import { usePerson } from "../hooks/usePerson";

// 5. Assets and styles
import "./App.css";
```

### Accessibility

**Every interactive element must be accessible:**

- Use semantic HTML (`<button>`, `<nav>`, `<main>`, etc.)
- Provide aria-labels for icon buttons
- Ensure keyboard navigation works
- Maintain focus management in modals/dialogs
- Test with screen readers when possible

```tsx
// ✅ GOOD
<button onClick={handleDelete} aria-label="Delete person">
  <TrashIcon />
</button>

// ❌ BAD
<div onClick={handleDelete}>
  <TrashIcon />
</div>
```

### Performance

**Trust the React Compiler first**, but watch for:

- Large list rendering — use virtualization if needed
- Heavy computations — consider Web Workers
- Large images — lazy load and optimize
- Bundle size — code-split routes

### Common Patterns

#### Conditional Rendering

```tsx
// Simple condition
{isLoading && <Spinner />}

// If/else
{isError ? <ErrorMessage /> : <Content />}

// Multiple conditions
{status === "idle" && <EmptyState />}
{status === "loading" && <Spinner />}
{status === "success" && <Results data={data} />}
{status === "error" && <ErrorMessage error={error} />}
```

#### Lists and Keys

```tsx
// Always use unique, stable keys
<ul>
  {people.map(person => (
    <li key={person.id}>  {/* Use ID, not index */}
      <PersonCard person={person} />
    </li>
  ))}
</ul>
```

#### Forms

```tsx
function ProfileForm({ onSave }: { onSave: (data: FormData) => void }) {
  const [name, setName] = useState("");

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    onSave({ name });
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="name">Name</label>
      <input
        id="name"
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
      />
      <button type="submit">Save</button>
    </form>
  );
}
```

## Backend Development Guidelines

### File Organization

```
apps/api/
├── src/
│   └── api/
│       ├── routes/          # API route handlers
│       ├── models/          # Pydantic models
│       ├── services/        # Business logic
│       ├── utils/           # Helper functions
│       ├── security/        # Auth and security
│       ├── enums.py         # Application enums
│       ├── settings.py      # Configuration
│       └── app.py           # FastAPI application
└── tests/
    ├── conftest.py          # Shared fixtures
    └── test_*.py            # Test modules
```

### FastAPI Endpoint Guidelines

#### 1. Async-First

**Always use async endpoints:**

```python
from fastapi import APIRouter

router = APIRouter()

@router.get('/users/{user_id}')
async def get_user(user_id: str) -> UserResponse:
    """Get user by ID."""
    user = await user_service.get_user(user_id)
    return UserResponse.model_validate(user)
```

**Key principles:**

- Use `async def` for all route handlers
- Use `await` for I/O operations (DB, HTTP, file access)
- Never use blocking sync calls inside async functions
- For unavoidable sync code, wrap with `asyncio.to_thread()`

#### 2. Pydantic Models

**Define explicit request/response models:**

```python
from pydantic import BaseModel, ConfigDict, Field

class PersonCreate(BaseModel):
    """Request model for creating a person."""
    
    model_config = ConfigDict(extra='forbid')
    
    name: str = Field(..., min_length=1, max_length=200)
    birth_year: int | None = Field(None, ge=1000, le=9999)
    wikitree_id: str | None = None

class PersonResponse(BaseModel):
    """Response model for person data."""
    
    model_config = ConfigDict(extra='forbid')
    
    id: str
    name: str
    birth_year: int | None
    wikitree_id: str | None
    created_at: str
```

**Best practices:**

- Use `ConfigDict(extra='forbid')` to reject unknown fields
- Add `Field()` constraints for validation
- Use descriptive docstrings
- Separate request and response models
- Use `model_validate()` for conversions

#### 3. Type Hints

**Always use type hints:**

```python
# ✅ GOOD
async def find_matches(
    gedcom_person: Person,
    threshold: float = 0.8
) -> list[Match]:
    """Find WikiTree matches for a GEDCOM person."""
    results: list[Match] = []
    # ...
    return results

# ❌ BAD - no type hints
async def find_matches(gedcom_person, threshold=0.8):
    results = []
    # ...
    return results
```

**Type hint standards:**

- Use `list[T]`, `dict[K, V]` (Python 3.12+ syntax)
- Use `T | None` instead of `Optional[T]`
- Type all function parameters and returns
- Use `typing.Protocol` for duck-typed interfaces
- Run `pyrefly check` to verify type safety

#### 4. Dependency Injection

**Use FastAPI's dependency injection:**

```python
from fastapi import Depends
from api.security import get_current_user

@router.get('/profile')
async def get_profile(
    user: User = Depends(get_current_user)
) -> ProfileResponse:
    """Get current user's profile."""
    return ProfileResponse.model_validate(user)
```

**Common dependencies:**

- Authentication: `Depends(get_current_user)`
- Database sessions: `Depends(get_db)`
- Service instances: `Depends(get_service)`

#### 5. Error Handling

**Use HTTPException for API errors:**

```python
from fastapi import HTTPException, status

@router.get('/person/{person_id}')
async def get_person(person_id: str) -> PersonResponse:
    """Get person by ID."""
    person = await person_service.get(person_id)
    
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Person {person_id} not found'
        )
    
    return PersonResponse.model_validate(person)
```

**Error handling patterns:**

- Use standard HTTP status codes
- Provide descriptive `detail` messages
- Log errors with context before raising
- Use custom exception handlers for domain errors

### Settings and Configuration

**Use Pydantic Settings:**

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings from environment."""
    
    model_config = SettingsConfigDict(env_file='.env')
    
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')
    database_url: str = Field(..., alias='DATABASE_URL')
    auth_disabled: bool = Field(default=False, alias='AUTH_DISABLED')

settings = Settings()  # pyrefly: ignore[missing-argument]
```

**Configuration best practices:**

- Load all config from environment variables
- Use `Field()` with `alias` for env var names
- Mark required fields with `...` (no default)
- Provide safe defaults for optional settings
- Validate at startup (fails fast if misconfigured)

### Testing Requirements

#### Every endpoint must have tests

Create test files in `tests/` directory:

```
test_health.py
test_auth.py
test_person.py
```

#### Test Structure

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_person_success(async_test_client: AsyncClient):
    """Test successful person retrieval."""
    # Arrange
    person_id = 'test-123'
    
    # Act
    response = await async_test_client.get(f'/person/{person_id}')
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data['id'] == person_id
    assert 'name' in data

@pytest.mark.asyncio
async def test_get_person_not_found(async_test_client: AsyncClient):
    """Test person not found error."""
    response = await async_test_client.get('/person/nonexistent')
    
    assert response.status_code == 404
    assert 'not found' in response.json()['detail'].lower()
```

#### Testing Guidelines

**Cover all paths:**

- Happy path (200 responses)
- Not found (404)
- Validation errors (422)
- Authentication errors (401)
- Authorization errors (403)

**Use fixtures:**

```python
# conftest.py
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
import pytest_asyncio

from api.app import app

@pytest_asyncio.fixture()
async def async_test_client() -> AsyncClient:
    """Async HTTP client for testing FastAPI app."""
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app),
            base_url='http://test'
        ) as client:
            yield client
```

**Test data patterns:**

- Use factories or builders for test data
- Clean up after each test
- Use `pytest-mock` for external dependencies
- Mock time-dependent behavior

### Code Quality Standards

#### Running Quality Checks

```bash
cd apps/api

# Install dev dependencies
pip install -e ".[dev]"

# Type checking
pyrefly check src/

# Linting
ruff check src/

# Formatting
ruff format src/

# Check formatting without changes
ruff format --check src/

# Testing
pytest -v

# Testing with coverage
pytest --cov=api --cov-report=term-missing
```

#### Code Style

**Follow PEP 8 and Ruff rules:**

- 80 character line length
- Single quotes for strings
- 4-space indentation
- Blank lines between imports and code
- Organize imports: stdlib, third-party, first-party

**Import organization:**

```python
# 1. Future imports
from __future__ import annotations

# 2. Standard library
import logging
from datetime import datetime

# 3. Third-party
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 4. First-party
from api.models.person import Person
from api.services.matching import MatchingService
```

### Common Patterns

#### Route Organization

```python
# routes/person.py
from fastapi import APIRouter, Depends, HTTPException, status

from api.models.person import PersonCreate, PersonResponse
from api.security import get_current_user

router = APIRouter(prefix='/person', tags=['person'])

@router.post('', status_code=status.HTTP_201_CREATED)
async def create_person(
    data: PersonCreate,
    user: User = Depends(get_current_user)
) -> PersonResponse:
    """Create a new person."""
    person = await person_service.create(data, user_id=user.id)
    return PersonResponse.model_validate(person)

@router.get('/{person_id}')
async def get_person(person_id: str) -> PersonResponse:
    """Get person by ID."""
    person = await person_service.get(person_id)
    
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Person {person_id} not found'
        )
    
    return PersonResponse.model_validate(person)
```

#### Service Layer

```python
# services/person.py
from api.models.person import Person

class PersonService:
    """Business logic for person operations."""
    
    async def get(self, person_id: str) -> Person | None:
        """Get person by ID."""
        # Database or API call
        result = await db.get_person(person_id)
        return Person.model_validate(result) if result else None
    
    async def create(
        self,
        data: PersonCreate,
        user_id: str
    ) -> Person:
        """Create a new person."""
        person_dict = data.model_dump()
        person_dict['user_id'] = user_id
        person_dict['created_at'] = datetime.utcnow().isoformat()
        
        result = await db.insert_person(person_dict)
        return Person.model_validate(result)
```

#### Async Context Managers

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info('Starting up...')
    await database.connect()
    
    yield
    
    # Shutdown
    logger.info('Shutting down...')
    await database.disconnect()

app = FastAPI(lifespan=lifespan)
```

## Pull Request Guidelines

**Every PR must:**

- Touch fewer than 10 files
- Be easy to review (< 400 lines changed preferred)
- Pass all tests (UI: `npm run test:ci`, API: `pytest`)
- Pass linting (UI: `npm run lint`, API: `ruff check`)
- Pass type checking (UI: `npm run build`, API: `pyrefly check`)
- Maintain or improve code coverage (target: 80%+)

**Before submitting (UI):**

```bash
cd apps/ui
npm run lint:fix
npm run format
npm run test
npm run build
```

**Before submitting (API):**

```bash
cd apps/api
ruff check src/
ruff format src/
pyrefly check src/
pytest -v
```

## Development Workflow

### Local Development

**UI:**

```bash
# Start dev server
cd apps/ui
npm run dev

# In another terminal - run tests in watch mode
npm run test:watch
```

**API:**

```bash
# Start dev server
cd apps/api
uvicorn api.app:app --reload

# In another terminal - run tests in watch mode
pytest -v --cov=api -x
```

### Adding a New UI Component

1. Create `src/components/MyComponent.tsx`
2. Define TypeScript interface for props
3. Implement component following guidelines above
4. Create `tests/MyComponent.test.tsx` with tests
5. Ensure tests pass: `npm run test`
6. Verify linting: `npm run lint`
7. Format code: `npm run format`

### Adding a New API Endpoint

1. Create or update route in `src/api/routes/`
2. Define Pydantic models in `src/api/models/`
3. Implement endpoint following guidelines above
4. Create tests in `tests/test_*.py`
5. Ensure tests pass: `pytest -v`
6. Verify linting: `ruff check src/`
7. Format code: `ruff format src/`
8. Check types: `pyrefly check src/`

### Debugging Tests

**UI:**

```bash
# Run tests in UI mode for debugging
npm run test:ui

# Run tests with console output
npm run test:watch

# Run specific test file
npm run test PersonCard.test
```

**API:**

```bash
# Run tests with verbose output
pytest -v -s

# Run specific test file
pytest tests/test_health.py -v

# Run specific test function
pytest tests/test_health.py::test_health_endpoint -v

# Run with debugger on failure
pytest --pdb
```

## Resources

### Frontend

- [React 19 Documentation](https://react.dev/)
- [Vite Documentation](https://vite.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Vitest Documentation](https://vitest.dev/)
- [React Compiler](https://react.dev/learn/react-compiler)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)

### Backend

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Python Type Hints (PEP 484)](https://peps.python.org/pep-0484/)
- [Async/Await in Python](https://docs.python.org/3/library/asyncio.html)

## Questions?

Check [`implementation-plan.md`](./implementation-plan.md) for the build plan and PR sequence.

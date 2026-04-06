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

- Python (planned)
- Backend tests in `apps/api/tests/`

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

## Pull Request Guidelines

**Every PR must:**

- Touch fewer than 10 files
- Be easy to review (< 400 lines changed preferred)
- Pass all tests (`npm run test:ci`)
- Pass linting (`npm run lint`)
- Pass type checking (`npm run build`)
- Maintain or improve code coverage (target: 80%+)

**Before submitting:**

```bash
cd apps/ui
npm run lint:fix
npm run format
npm run test
npm run build
```

## Development Workflow

### Local Development

```bash
# Start dev server
cd apps/ui
npm run dev

# In another terminal - run tests in watch mode
npm run test:watch
```

### Adding a New Component

1. Create `src/components/MyComponent.tsx`
2. Define TypeScript interface for props
3. Implement component following guidelines above
4. Create `tests/MyComponent.test.tsx` with tests
5. Ensure tests pass: `npm run test`
6. Verify linting: `npm run lint`
7. Format code: `npm run format`

### Debugging Tests

```bash
# Run tests in UI mode for debugging
npm run test:ui

# Run tests with console output
npm run test:watch

# Run specific test file
npm run test PersonCard.test
```

## Resources

- [React 19 Documentation](https://react.dev/)
- [Vite Documentation](https://vite.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Vitest Documentation](https://vitest.dev/)
- [React Compiler](https://react.dev/learn/react-compiler)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)

## Questions?

Check [`implementation-plan.md`](./implementation-plan.md) for the build plan and PR sequence.

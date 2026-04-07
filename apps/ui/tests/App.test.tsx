import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from '../src/App';
import * as auth from '../src/lib/auth';
import type { AuthState } from '../src/lib/auth';

// Mock the auth module
vi.mock('../src/lib/auth', async () => {
  const actual = await vi.importActual('../src/lib/auth');
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

// Mock GoogleSignInButton component
vi.mock('../src/components/GoogleSignInButton', () => ({
  GoogleSignInButton: () => <div data-testid="google-signin-button">Sign In with Google</div>,
}));

describe('App', () => {
  const mockUseAuth = vi.mocked(auth.useAuth);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state', () => {
    const loadingState: AuthState = { status: 'loading' };
    mockUseAuth.mockReturnValue({
      authState: loadingState,
      loginWithGoogle: vi.fn(),
      logout: vi.fn(),
    });

    render(<App />);

    expect(screen.getByTestId('loading-state')).toBeDefined();
    expect(screen.getByText('Loading...')).toBeDefined();
  });

  it('renders unauthenticated state with sign-in button', () => {
    const unauthenticatedState: AuthState = { status: 'unauthenticated' };
    mockUseAuth.mockReturnValue({
      authState: unauthenticatedState,
      loginWithGoogle: vi.fn(),
      logout: vi.fn(),
    });

    render(<App />);

    const heading = screen.getByRole('heading', {
      name: /wikitree intelligence/i,
    });
    expect(heading).toBeDefined();

    const subtitle = screen.getByText(/local-first genealogy software/i);
    expect(subtitle).toBeDefined();

    expect(screen.getByText(/research-grade genealogy/i)).toBeDefined();
    expect(screen.getByText(/one workspace for the real decisions/i)).toBeDefined();

    const signInButton = screen.getByTestId('google-signin-button');
    expect(signInButton).toBeDefined();
  });

  it('renders authenticated state with user info', () => {
    const authenticatedState: AuthState = {
      status: 'authenticated',
      user: {
        userid: 'test-user-123',
        email: 'test@example.com',
        name: 'Test User',
      },
    };
    mockUseAuth.mockReturnValue({
      authState: authenticatedState,
      loginWithGoogle: vi.fn(),
      logout: vi.fn(),
    });

    render(<App />);

    const loggedInHeading = screen.getByRole('heading', {
      name: /genealogy detective desk/i,
    });
    expect(loggedInHeading).toBeDefined();

    expect(screen.getByText(/test-user-123/i)).toBeDefined();
    expect(screen.getByText(/test@example.com/i)).toBeDefined();
    expect(screen.getAllByText(/Test User/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/import gedcom/i)).toBeDefined();
    expect(screen.getByText(/clear existing data/i)).toBeDefined();

    const logoutButton = screen.getByRole('button', { name: /logout/i });
    expect(logoutButton).toBeDefined();
  });
});

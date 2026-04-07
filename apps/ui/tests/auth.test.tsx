import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthProvider, useAuth } from '../src/lib/auth';
import type { User } from '../src/types/api';
import * as api from '../src/lib/api';

// Mock the API module
vi.mock('../src/lib/api', () => ({
  login: vi.fn(),
  logout: vi.fn(),
  getCurrentUser: vi.fn(),
}));

// Test component that uses the auth context
function TestComponent() {
  const { authState, loginWithGoogle, logout } = useAuth();

  const handleLogin = async () => {
    try {
      await loginWithGoogle('test-token');
    } catch {
      // Error is caught and logged by AuthProvider
    }
  };

  return (
    <div>
      <div data-testid="auth-status">{authState.status}</div>
      {authState.status === 'authenticated' && (
        <div data-testid="user-id">{authState.user.userid}</div>
      )}
      <button onClick={handleLogin}>Login</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
}

describe('AuthProvider', () => {
  const mockUser: User = {
    userid: 'test-123',
    email: 'test@example.com',
    name: 'Test User',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts in loading state', () => {
    vi.mocked(api.getCurrentUser).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('auth-status').textContent).toBe('loading');
  });

  it('transitions to authenticated when user is logged in', async () => {
    vi.mocked(api.getCurrentUser).mockResolvedValueOnce(mockUser);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('authenticated');
    });

    expect(screen.getByTestId('user-id').textContent).toBe('test-123');
  });

  it('transitions to unauthenticated when no user is logged in', async () => {
    vi.mocked(api.getCurrentUser).mockResolvedValueOnce(null);

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated');
    });
  });

  it('handles auth check errors by setting unauthenticated', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    vi.mocked(api.getCurrentUser).mockRejectedValueOnce(new Error('Network error'));

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated');
    });

    expect(consoleErrorSpy).toHaveBeenCalledWith('Auth check failed:', expect.any(Error));

    consoleErrorSpy.mockRestore();
  });

  it('ignores abort errors when component unmounts', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const abortError = new Error('Aborted');
    abortError.name = 'AbortError';
    vi.mocked(api.getCurrentUser).mockRejectedValueOnce(abortError);

    const { unmount } = render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    unmount();

    await waitFor(() => {
      // Should not log abort errors
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });

    consoleErrorSpy.mockRestore();
  });

  it('successfully logs in with Google token', async () => {
    vi.mocked(api.getCurrentUser).mockResolvedValueOnce(null);
    vi.mocked(api.login).mockResolvedValueOnce(mockUser);

    const user = userEvent.setup();

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Wait for initial auth check to complete
    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated');
    });

    // Click login button
    const loginButton = screen.getByRole('button', { name: /login/i });
    await user.click(loginButton);

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('authenticated');
    });

    expect(api.login).toHaveBeenCalledWith('test-token');
    expect(screen.getByTestId('user-id').textContent).toBe('test-123');
  });

  it('handles login errors', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    vi.mocked(api.getCurrentUser).mockResolvedValueOnce(null);
    vi.mocked(api.login).mockRejectedValueOnce(new Error('Login failed'));

    const user = userEvent.setup();

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Wait for initial auth check
    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated');
    });

    const loginButton = screen.getByRole('button', { name: /login/i });

    // Click button - error is caught and logged, not thrown
    await user.click(loginButton);

    // Wait for error to be logged
    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith('Login failed:', expect.any(Error));
    });

    expect(consoleErrorSpy).toHaveBeenCalledWith('Login failed:', expect.any(Error));

    consoleErrorSpy.mockRestore();
  });

  it('successfully logs out', async () => {
    vi.mocked(api.getCurrentUser).mockResolvedValueOnce(mockUser);
    vi.mocked(api.logout).mockResolvedValueOnce(undefined);

    const user = userEvent.setup();

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Wait for authenticated state
    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('authenticated');
    });

    // Click logout button
    const logoutButton = screen.getByRole('button', { name: /logout/i });
    await user.click(logoutButton);

    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated');
    });

    expect(api.logout).toHaveBeenCalled();
  });

  it('sets unauthenticated even when logout fails', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    vi.mocked(api.getCurrentUser).mockResolvedValueOnce(mockUser);
    vi.mocked(api.logout).mockRejectedValueOnce(new Error('Logout failed'));

    const user = userEvent.setup();

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    // Wait for authenticated state
    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('authenticated');
    });

    // Click logout button
    const logoutButton = screen.getByRole('button', { name: /logout/i });
    await user.click(logoutButton);

    // Should still set unauthenticated even though logout failed
    await waitFor(() => {
      expect(screen.getByTestId('auth-status').textContent).toBe('unauthenticated');
    });

    expect(consoleErrorSpy).toHaveBeenCalledWith('Logout failed:', expect.any(Error));

    consoleErrorSpy.mockRestore();
  });

  it('throws error when useAuth is used outside AuthProvider', () => {
    // Suppress expected console errors
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(<TestComponent />);
    }).toThrow('useAuth must be used within AuthProvider');

    consoleErrorSpy.mockRestore();
  });
});

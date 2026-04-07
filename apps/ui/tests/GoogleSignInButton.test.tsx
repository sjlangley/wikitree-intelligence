import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { GoogleSignInButton } from '../src/components/GoogleSignInButton';
import * as auth from '../src/lib/auth';

// Mock the auth module
vi.mock('../src/lib/auth', async () => {
  const actual = await vi.importActual('../src/lib/auth');
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

describe('GoogleSignInButton', () => {
  const mockLoginWithGoogle = vi.fn();
  const mockUseAuth = vi.mocked(auth.useAuth);

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      authState: { status: 'unauthenticated' },
      loginWithGoogle: mockLoginWithGoogle,
      logout: vi.fn(),
    });

    // Clear environment variables
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'test-client-id');

    // Mock window.google
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (window as any).google;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('shows loading state when Google SDK is not loaded', () => {
    render(<GoogleSignInButton />);

    expect(screen.getByText('Loading sign-in button...')).toBeDefined();
  });

  it('shows error when VITE_GOOGLE_CLIENT_ID is not set', () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '');

    // Set Google as loaded
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).google = { accounts: { id: {} } };

    render(<GoogleSignInButton />);

    expect(screen.getByText(/Google Sign-In is not configured/i)).toBeDefined();
  });

  it('renders button container when Google SDK is loaded', async () => {
    // Mock Google SDK
    const mockInitialize = vi.fn();
    const mockRenderButton = vi.fn();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).google = {
      accounts: {
        id: {
          initialize: mockInitialize,
          renderButton: mockRenderButton,
        },
      },
    };

    render(<GoogleSignInButton />);

    await waitFor(() => {
      expect(screen.getByTestId('google-signin-button')).toBeDefined();
    });

    // Verify Google SDK was initialized
    expect(mockInitialize).toHaveBeenCalledWith({
      client_id: 'test-client-id',
      callback: expect.any(Function),
    });

    expect(mockRenderButton).toHaveBeenCalled();
  });

  it('calls loginWithGoogle when Google callback is triggered', async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let capturedCallback: any;

    const mockInitialize = vi.fn((config) => {
      capturedCallback = config.callback;
    });
    const mockRenderButton = vi.fn();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).google = {
      accounts: {
        id: {
          initialize: mockInitialize,
          renderButton: mockRenderButton,
        },
      },
    };

    render(<GoogleSignInButton />);

    await waitFor(() => {
      expect(mockInitialize).toHaveBeenCalled();
    });

    // Simulate Google callback
    const testCredential = 'test-google-token';
    await capturedCallback({ credential: testCredential });

    expect(mockLoginWithGoogle).toHaveBeenCalledWith(testCredential);
  });

  it('handles login errors gracefully', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    mockLoginWithGoogle.mockRejectedValue(new Error('Login failed'));

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let capturedCallback: any;

    const mockInitialize = vi.fn((config) => {
      capturedCallback = config.callback;
    });
    const mockRenderButton = vi.fn();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).google = {
      accounts: {
        id: {
          initialize: mockInitialize,
          renderButton: mockRenderButton,
        },
      },
    };

    render(<GoogleSignInButton />);

    await waitFor(() => {
      expect(mockInitialize).toHaveBeenCalled();
    });

    // Simulate Google callback with error
    await capturedCallback({ credential: 'test-token' });

    expect(consoleErrorSpy).toHaveBeenCalledWith('Login error:', expect.any(Error));

    consoleErrorSpy.mockRestore();
  });
});

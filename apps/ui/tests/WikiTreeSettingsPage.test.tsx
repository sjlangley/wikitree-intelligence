/**
 * Tests for WikiTreeSettingsPage component
 */

import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { WikiTreeSettingsPage } from '../components/WikiTreeSettingsPage';

// Mock fetch with proper typing
const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

// Helper to create a mock Response
function createMockResponse(data: unknown, options: Partial<Response> = {}) {
  return {
    ok: true,
    status: 200,
    ...options,
    json: async () => data,
  } as Response;
}

describe('WikiTreeSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockClear();

    // Reset window.location
    Object.defineProperty(window, 'location', {
      value: { href: 'http://localhost/', search: '', pathname: '/' },
      writable: true,
      configurable: true,
    });
  });

  it('renders loading state initially', () => {
    mockFetch.mockImplementation(() => new Promise<Response>(() => undefined));

    render(<WikiTreeSettingsPage />);

    expect(screen.getByText(/loading connection status/i)).toBeInTheDocument();
  });

  it('renders not connected state', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        is_connected: false,
        wikitree_user_id: null,
        wikitree_user_name: null,
        connected_at: null,
        expires_at: null,
        last_verified_at: null,
      })
    );

    render(<WikiTreeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/not connected/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /connect wikitree/i })).toBeInTheDocument();
  });

  it('renders connected state', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        is_connected: true,
        wikitree_user_id: 12345,
        wikitree_user_name: 'TestUser-1',
        connected_at: '2026-04-09T10:00:00Z',
        expires_at: '2026-05-09T10:00:00Z',
        last_verified_at: null,
      })
    );

    render(<WikiTreeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/connected/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/TestUser-1/i)).toBeInTheDocument();
    expect(screen.getByText(/12345/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /disconnect wikitree/i })).toBeInTheDocument();
  });

  it('handles connect button click', async () => {
    const user = userEvent.setup();

    // Mock status fetch
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        is_connected: false,
        wikitree_user_id: null,
        wikitree_user_name: null,
        connected_at: null,
        expires_at: null,
        last_verified_at: null,
      })
    );

    // Mock initiate fetch
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        login_url: 'https://api.wikitree.com/api.php?action=clientLogin&...',
      })
    );

    render(<WikiTreeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /connect wikitree/i })).toBeInTheDocument();
    });

    const connectButton = screen.getByRole('button', { name: /connect wikitree/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/wikitree/connect/initiate',
        expect.objectContaining({
          method: 'POST',
        })
      );
    });
  });

  it('handles disconnect button click', async () => {
    const user = userEvent.setup();

    // Mock confirm
    window.confirm = vi.fn(() => true);

    // Mock status fetch (connected)
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        is_connected: true,
        wikitree_user_id: 12345,
        wikitree_user_name: 'TestUser-1',
        connected_at: '2026-04-09T10:00:00Z',
        expires_at: '2026-05-09T10:00:00Z',
        last_verified_at: null,
      })
    );

    // Mock disconnect fetch
    mockFetch.mockResolvedValueOnce(createMockResponse(null, { status: 204 }));

    // Mock status fetch after disconnect
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        is_connected: false,
        wikitree_user_id: null,
        wikitree_user_name: null,
        connected_at: null,
        expires_at: null,
        last_verified_at: null,
      })
    );

    render(<WikiTreeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /disconnect wikitree/i })).toBeInTheDocument();
    });

    const disconnectButton = screen.getByRole('button', { name: /disconnect wikitree/i });
    await user.click(disconnectButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/wikitree/disconnect', {
        method: 'POST',
      });
    });
  });

  it('displays error message on fetch failure', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    render(<WikiTreeSettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });
  });
});

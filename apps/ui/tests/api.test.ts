import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { login, logout, getCurrentUser } from '../src/lib/api';

describe('API Client', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    // Mock fetch
    global.fetch = vi.fn();
    // Mock environment variable
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000');
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  describe('login', () => {
    it('successfully logs in with valid token', async () => {
      const mockUser = {
        userid: 'test-123',
        email: 'test@example.com',
        name: 'Test User',
      };

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      });

      const result = await login('test-google-token');

      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/auth/login', {
        method: 'POST',
        headers: {
          Authorization: 'Bearer test-google-token',
        },
        credentials: 'include',
      });

      expect(result).toEqual(mockUser);
    });

    it('throws error when login fails', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      await expect(login('invalid-token')).rejects.toThrow('Login failed');
    });

    it('uses relative path when VITE_API_BASE_URL is not set', async () => {
      vi.stubEnv('VITE_API_BASE_URL', '');

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ userid: 'test' }),
      });

      await login('test-token');

      expect(global.fetch).toHaveBeenCalledWith('/auth/login', expect.any(Object));
    });
  });

  describe('getCurrentUser', () => {
    it('returns user when authenticated', async () => {
      const mockUser = {
        userid: 'test-123',
        email: 'test@example.com',
        name: 'Test User',
      };

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockUser,
      });

      const result = await getCurrentUser();

      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/user/current', {
        credentials: 'include',
        signal: undefined,
      });

      expect(result).toEqual(mockUser);
    });

    it('returns null when not authenticated (401)', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      const result = await getCurrentUser();

      expect(result).toBeNull();
    });

    it('throws error for non-401 failures', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(getCurrentUser()).rejects.toThrow('Failed to fetch current user');
    });

    it('passes abort signal when provided', async () => {
      const abortController = new AbortController();

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ userid: 'test' }),
      });

      await getCurrentUser(abortController.signal);

      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/user/current', {
        credentials: 'include',
        signal: abortController.signal,
      });
    });
  });

  describe('logout', () => {
    it('successfully logs out', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
      });

      await logout();

      expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
    });

    it('throws error when logout fails', async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(logout()).rejects.toThrow('Logout failed');
    });
  });
});

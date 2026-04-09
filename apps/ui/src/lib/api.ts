/**
 * API client for backend communication
 * All requests include credentials to send session cookies
 */

import type { User } from '../types/api';

function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL || '';
}

/**
 * Login with Google ID token
 */
export async function login(googleIdToken: string): Promise<User> {
  const response = await fetch(`${getApiBaseUrl()}/auth/login`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${googleIdToken}`,
    },
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Login failed');
  }

  return response.json();
}

/**
 * Get current authenticated user
 * Returns null if not authenticated (401 response)
 */
export async function getCurrentUser(signal?: AbortSignal): Promise<User | null> {
  const response = await fetch(`${getApiBaseUrl()}/user/current`, {
    credentials: 'include',
    signal,
  });

  if (response.status === 401) {
    return null;
  }

  if (!response.ok) {
    throw new Error('Failed to fetch current user');
  }

  return response.json();
}

/**
 * Logout current user
 */
export async function logout(): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Logout failed');
  }
}

/**
 * WikiTree API types
 */
export interface WikiTreeConnectionStatus {
  is_connected: boolean;
  wikitree_user_id: number | null;
  wikitree_user_name: string | null;
  connected_at: string | null;
  expires_at: string | null;
  last_verified_at: string | null;
}

export interface WikiTreeConnectInitiateRequest {
  return_url: string;
}

export interface WikiTreeConnectInitiateResponse {
  login_url: string;
}

export interface WikiTreeConnectCallbackRequest {
  authcode: string;
}

/**
 * Get WikiTree connection status
 */
export async function getWikiTreeStatus(): Promise<WikiTreeConnectionStatus> {
  const response = await fetch(`${getApiBaseUrl()}/api/wikitree/status`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to fetch WikiTree status');
  }

  return response.json();
}

/**
 * Initiate WikiTree connection
 */
export async function initiateWikiTreeConnection(
  returnUrl: string
): Promise<WikiTreeConnectInitiateResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/wikitree/connect/initiate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ return_url: returnUrl }),
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to initiate WikiTree connection');
  }

  return response.json();
}

/**
 * Handle WikiTree OAuth callback
 */
export async function handleWikiTreeCallback(
  authcode: string
): Promise<WikiTreeConnectionStatus> {
  const response = await fetch(`${getApiBaseUrl()}/api/wikitree/connect/callback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ authcode }),
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Failed to connect to WikiTree');
  }

  return response.json();
}

/**
 * Disconnect from WikiTree
 */
export async function disconnectWikiTree(): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/api/wikitree/disconnect`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok && response.status !== 204) {
    throw new Error('Failed to disconnect from WikiTree');
  }
}

/**
 * WikiTree connection settings page
 * Manages WikiTree authentication and connection status
 */

import { useEffect, useState } from 'react';

interface WikiTreeConnectionStatus {
  is_connected: boolean;
  wikitree_user_id: number | null;
  wikitree_user_name: string | null;
  connected_at: string | null;
  expires_at: string | null;
  last_verified_at: string | null;
}

const API_BASE = '/api/wikitree';

interface WikiTreeSettingsPageProps {
  onStatusChange?: () => void;
}

export function WikiTreeSettingsPage(props: WikiTreeSettingsPageProps = {}) {
  const { onStatusChange } = props;
  const [status, setStatus] = useState<WikiTreeConnectionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  // Fetch connection status on mount
  useEffect(() => {
    fetchStatus();
  }, []);

  // Handle OAuth callback with authcode
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const authcode = urlParams.get('authcode');

    if (authcode) {
      handleCallback(authcode);
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  async function fetchStatus() {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE}/status`);

      if (!response.ok) {
        throw new Error('Failed to fetch connection status');
      }

      const data = await response.json();
      setStatus(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function handleConnect() {
    try {
      setIsConnecting(true);
      setError(null);

      // Get the current URL as return URL
      const returnUrl = window.location.href;

      const response = await fetch(`${API_BASE}/connect/initiate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ return_url: returnUrl }),
      });

      if (!response.ok) {
        throw new Error('Failed to initiate connection');
      }

      const data = await response.json();

      // Redirect to WikiTree login
      window.location.href = data.login_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setIsConnecting(false);
    }
  }

  async function handleCallback(authcode: string) {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE}/connect/callback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ authcode }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to connect');
      }

      const data = await response.json();
      setStatus(data);
      // Notify parent component of status change
      if (onStatusChange) {
        onStatusChange();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleDisconnect() {
    if (!confirm('Are you sure you want to disconnect from WikiTree?')) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE}/disconnect`, {
        method: 'POST',
      });

      if (!response.ok && response.status !== 204) {
        throw new Error('Failed to disconnect');
      }

      // Refresh status
      await fetchStatus();
      // Notify parent component of status change
      if (onStatusChange) {
        onStatusChange();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  }

  if (loading && !status) {
    return (
      <div className="panel-card">
        <h2>WikiTree Connection</h2>
        <p>Loading connection status...</p>
      </div>
    );
  }

  return (
    <div className="panel-card">
      <h2>WikiTree Connection</h2>

      {error && (
        <div className="alert alert-error" role="alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      {status && status.is_connected ? (
        <div className="connection-status connection-status-active">
          <div className="status-header">
            <span className="status-pill status-pill-confirmed">Connected</span>
            <p className="status-meta">
              Connected as <strong>{status.wikitree_user_name}</strong>
            </p>
          </div>

          <div className="status-details">
            <dl className="detail-list">
              <div className="detail-item">
                <dt>WikiTree User ID:</dt>
                <dd>{status.wikitree_user_id}</dd>
              </div>
              <div className="detail-item">
                <dt>Connected at:</dt>
                <dd>{status.connected_at ? new Date(status.connected_at).toLocaleString() : 'Unknown'}</dd>
              </div>
              <div className="detail-item">
                <dt>Expires at:</dt>
                <dd>{status.expires_at ? new Date(status.expires_at).toLocaleString() : 'Unknown'}</dd>
              </div>
              {status.last_verified_at && (
                <div className="detail-item">
                  <dt>Last verified:</dt>
                  <dd>{new Date(status.last_verified_at).toLocaleString()}</dd>
                </div>
              )}
            </dl>
          </div>

          <div className="action-stack">
            <button
              onClick={handleDisconnect}
              className="button-secondary"
              type="button"
              disabled={loading}
            >
              {loading ? 'Disconnecting...' : 'Disconnect WikiTree'}
            </button>
          </div>
        </div>
      ) : (
        <div className="connection-status connection-status-inactive">
          <div className="status-header">
            <span className="status-pill status-pill-review">Not Connected</span>
            <p className="status-explanation">
              Connect your WikiTree account to access private profiles and enable matching.
            </p>
          </div>

          <div className="action-stack">
            <button
              onClick={handleConnect}
              className="button-primary"
              type="button"
              disabled={isConnecting}
            >
              {isConnecting ? 'Connecting...' : 'Connect WikiTree'}
            </button>
          </div>

          <details className="connection-help">
            <summary>Why connect WikiTree?</summary>
            <p>
              Connecting your WikiTree account allows WikiTree Intelligence to:
            </p>
            <ul>
              <li>Access your private profiles and trusted connections</li>
              <li>Match GEDCOM records against your WikiTree network</li>
              <li>Suggest merges and corrections</li>
              <li>Respect privacy settings when importing</li>
            </ul>
            <p>
              Your WikiTree session is stored securely and expires after 30 days of inactivity.
            </p>
          </details>
        </div>
      )}
    </div>
  );
}

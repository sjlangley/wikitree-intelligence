/**
 * Logged-in screen component
 * Displays user information and logout button
 */

import { useAuth } from '../lib/auth';
import { WikiTreeSettingsPage } from './WikiTreeSettingsPage';
import { useEffect, useState } from 'react';
import type { User } from '../types/api';

interface LoggedInScreenProps {
  user: User;
}

interface WikiTreeStatus {
  is_connected: boolean;
}

export function LoggedInScreen({ user }: LoggedInScreenProps) {
  const { logout } = useAuth();
  const [wikiTreeConnected, setWikiTreeConnected] = useState(false);

  const fetchWikiTreeStatus = () => {
    fetch('/api/wikitree/status')
      .then(res => res.json())
      .then((data: WikiTreeStatus) => {
        setWikiTreeConnected(data.is_connected);
      })
      .catch(() => {
        // Ignore errors, default to disconnected
        setWikiTreeConnected(false);
      });
  };

  useEffect(() => {
    // Check WikiTree connection status on mount
    fetchWikiTreeStatus();
  }, []);

  async function handleLogout() {
    await logout();
  }

  // TODO: Replace this empty-state home screen with real import status and workspace
  // routing once GEDCOM jobs and review queues exist.
  return (
    <main className="workbench-shell">
      <header className="app-topbar">
        <div>
          <p className="section-eyebrow">WikiTree Intelligence</p>
          <h1 className="app-title">Genealogy detective desk</h1>
        </div>
        <div className="topbar-actions">
          <div className="user-badge">
            <span className="user-badge-label">Signed in</span>
            <strong>{user.name || user.email || user.userid}</strong>
          </div>
          <button onClick={handleLogout} className="button-secondary" type="button">
            Logout
          </button>
        </div>
      </header>

      <section className="workspace-card">
        <div className="workspace-summary workspace-summary-empty">
          <div>
            <p className="section-eyebrow">No import in progress</p>
            <h2>Start with a GEDCOM, then work outward.</h2>
            <p>
              Connect to WikiTree in the sidebar to enable profile matching, then import a GEDCOM file
              to begin reconciling your tree.
            </p>
          </div>
          <div className="status-row" role="group" aria-label="Session status">
            <span className="status-pill status-pill-confirmed">Google session active</span>
            <span className={`status-pill ${wikiTreeConnected ? 'status-pill-confirmed' : 'status-pill-review'}`}>
              {wikiTreeConnected ? 'WikiTree connected' : 'WikiTree not connected'}
            </span>
          </div>
        </div>

        <div className="home-grid">
          <section className="home-main">
            <div className="panel-card hero-card">
              <h3>Entry menu</h3>
              <div className="action-stack action-stack-roomy">
                <button
                  className="button-primary"
                  type="button"
                  disabled
                  title="Coming soon: GEDCOM import is not available yet."
                >
                  Import GEDCOM
                </button>
                <button
                  className="button-secondary"
                  type="button"
                  onClick={() => {
                    document.querySelector('.home-sidebar')?.scrollIntoView({ behavior: 'smooth' });
                  }}
                >
                  Connect WikiTree
                </button>
                <button
                  className="button-secondary"
                  type="button"
                  disabled
                  title="Coming soon: resume import is not available yet."
                >
                  Resume previous import
                </button>
                <button
                  className="button-secondary button-danger"
                  type="button"
                  disabled
                  title="Coming soon: clearing existing data is not available yet."
                >
                  Clear existing data
                </button>
                <p className="section-eyebrow" aria-live="polite">
                  GEDCOM import and data management features are coming soon.
                </p>
              </div>
            </div>

            <div className="panel-card">
              <h3>What happens next</h3>
              <div className="record-list">
                <div className="record-row">
                  <strong>1. Import one GEDCOM</strong>
                  <span>
                    Store the file locally, queue the job, and normalize people and relationships.
                  </span>
                </div>
                <div className="record-row">
                  <strong>2. Anchor one known person</strong>
                  <span>
                    Pick a person you trust and connect them to the right WikiTree profile.
                  </span>
                </div>
                <div className="record-row">
                  <strong>3. Review only the interesting cases</strong>
                  <span>
                    Possible matches, missing profiles, and conflicting facts rise to the top.
                  </span>
                </div>
              </div>
            </div>
          </section>

          <aside className="home-sidebar">
            <WikiTreeSettingsPage onStatusChange={fetchWikiTreeStatus} />

            <div className="panel-card panel-card-muted">
              <h3>User session</h3>
              <dl className="detail-list">
                <div>
                  <dt>User ID</dt>
                  <dd>{user.userid}</dd>
                </div>
                {user.name && (
                  <div>
                    <dt>Name</dt>
                    <dd>{user.name}</dd>
                  </div>
                )}
                {user.email && (
                  <div>
                    <dt>Email</dt>
                    <dd>{user.email}</dd>
                  </div>
                )}
              </dl>
            </div>

            <div className="panel-card">
              <h3>Before you start</h3>
              <p>
                WikiTree is read-only from the API side. This app should help you find safe existing
                matches first, then hand off missing profiles or extra facts for deliberate review.
              </p>
              <p>
                The home screen stays simple until an import exists. Then it should switch from
                “menu” to “workspace”.
              </p>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

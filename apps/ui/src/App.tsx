import { useAuth } from './lib/auth';
import { GoogleSignInButton } from './components/GoogleSignInButton';
import { LoggedInScreen } from './components/LoggedInScreen';
import './App.css';

export default function App() {
  const { authState } = useAuth();

  // Loading state
  if (authState.status === 'loading') {
    return (
      <div className="loading-shell">
        <div className="text-xl" data-testid="loading-state">
          Loading...
        </div>
      </div>
    );
  }

  // Authenticated state - show user info
  if (authState.status === 'authenticated') {
    return <LoggedInScreen user={authState.user} />;
  }

  return (
    <main className="marketing-shell">
      <section className="landing-hero">
        <div className="landing-copy">
          <p className="section-eyebrow">Editorial Archive Workbench</p>
          <h1>WikiTree Intelligence</h1>
          <p className="landing-lede">
            Local-first genealogy software for duplicate-safe discovery, evidence-backed matching,
            and careful reconciliation with WikiTree.
          </p>
          <div className="landing-actions">
            <div className="signin-panel">
              <p className="signin-kicker">
                Sign in to restore your workbench, queue state, and review history.
              </p>
              <GoogleSignInButton />
            </div>
            <div className="hero-note">
              <strong>The job is not bulk import.</strong>
              <p>
                The job is finding the person who probably already exists, proving it with sources,
                and surfacing the places where your tree and WikiTree genuinely diverge.
              </p>
            </div>
          </div>
        </div>

        <section className="landing-panel" aria-label="Product promise">
          <div className="metric-grid">
            <article className="metric-card">
              <span className="metric-label">Resolved</span>
              <strong>Ready to reconcile</strong>
              <p>Confirmed links you do not need to think about again.</p>
            </article>
            <article className="metric-card">
              <span className="metric-label">Needs review</span>
              <strong>Human judgment needed</strong>
              <p>Possible matches that still need a human call.</p>
            </article>
            <article className="metric-card">
              <span className="metric-label">Missing</span>
              <strong>Manual creation possible</strong>
              <p>Profiles the API could not match and you may need to create manually.</p>
            </article>
          </div>

          <div className="promise-card">
            <h2>Research-grade genealogy, without the old-software smell.</h2>
            <p>
              Keep the warmth of archival work. Keep the rigor of a serious tool. Lose the scrapbook
              UI and dashboard-card sludge.
            </p>
          </div>
        </section>
      </section>

      <section className="landing-section">
        <div className="landing-section-header">
          <p className="section-eyebrow">Why this exists</p>
          <h2>One workspace for the real decisions</h2>
          <p>
            A person page, a candidate comparison, and an evidence rail. That is the whole game.
          </p>
        </div>

        <div className="principles-grid">
          <article className="principle-card">
            <h3>Duplicate-safe matching</h3>
            <p>
              Search first, score candidates transparently, and only link when the evidence is real.
            </p>
          </article>
          <article className="principle-card">
            <h3>Evidence packets</h3>
            <p>Keep the sources, conflicts, and provenance visible beside every decision.</p>
          </article>
          <article className="principle-card">
            <h3>Resumable research</h3>
            <p>Large GEDCOM imports should survive restarts, pauses, and long review sessions.</p>
          </article>
        </div>
      </section>
    </main>
  );
}

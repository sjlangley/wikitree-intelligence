import { useAuth } from './lib/auth';
import { GoogleSignInButton } from './components/GoogleSignInButton';
import { LoggedInScreen } from './components/LoggedInScreen';
import './App.css';

export default function App() {
  const { authState } = useAuth();

  // Loading state
  if (authState.status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center">
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

  // Unauthenticated state - show sign-in button
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="login-container">
        <h1>WikiTree Intelligence</h1>
        <p className="subtitle">
          Local-first genealogy workbench for reconciling GEDCOM data with WikiTree
        </p>
        <div className="signin-section">
          <GoogleSignInButton />
        </div>
      </div>
    </div>
  );
}

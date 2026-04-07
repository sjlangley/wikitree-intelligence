/**
 * Logged-in screen component
 * Displays user information and logout button
 */

import { useAuth } from '../lib/auth';
import type { User } from '../types/api';

interface LoggedInScreenProps {
  user: User;
}

export function LoggedInScreen({ user }: LoggedInScreenProps) {
  const { logout } = useAuth();

  async function handleLogout() {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  }

  return (
    <div className="logged-in-screen">
      <h1>WikiTree Intelligence</h1>

      <div className="user-info">
        <h2>You are logged in</h2>

        <div className="user-details">
          <p>
            <strong>User ID:</strong> {user.userid}
          </p>
          {user.name && (
            <p>
              <strong>Name:</strong> {user.name}
            </p>
          )}
          {user.email && (
            <p>
              <strong>Email:</strong> {user.email}
            </p>
          )}
        </div>

        <button onClick={handleLogout} className="logout-button">
          Logout
        </button>
      </div>

      <div className="info-message">
        <p>
          Authentication is working end-to-end! The user information above was fetched from the{' '}
          <code>/user/current</code> API endpoint.
        </p>
      </div>
    </div>
  );
}

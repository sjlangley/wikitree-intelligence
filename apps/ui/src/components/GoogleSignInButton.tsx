/**
 * Google Sign-In Button Component
 * Uses Google Identity Services to render the sign-in button
 */

import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../lib/auth';

const GOOGLE_SDK_TIMEOUT_MS = 10000; // 10 seconds

export function GoogleSignInButton() {
  const buttonRef = useRef<HTMLDivElement>(null);
  const { loginWithGoogle } = useAuth();
  const [isGoogleLoaded, setIsGoogleLoaded] = useState(() => !!window.google);
  const [sdkLoadError, setSdkLoadError] = useState(false);
  const initializationRef = useRef(false);
  
  // Read env var inside component for better testability
  const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

  // Wait for Google Identity Services script to load
  useEffect(() => {
    if (window.google) {
      return;
    }

    let pollCount = 0;
    const maxPolls = GOOGLE_SDK_TIMEOUT_MS / 100;

    // Poll for Google script availability with timeout
    const checkGoogle = setInterval(() => {
      if (window.google) {
        setIsGoogleLoaded(true);
        clearInterval(checkGoogle);
      } else {
        pollCount++;
        if (pollCount >= maxPolls) {
          setSdkLoadError(true);
          clearInterval(checkGoogle);
        }
      }
    }, 100);

    return () => clearInterval(checkGoogle);
  }, []);

  // Initialize Google Sign-In button once script is loaded
  useEffect(() => {
    if (!isGoogleLoaded || !window.google || !buttonRef.current || !GOOGLE_CLIENT_ID) {
      return;
    }

    // Prevent double-initialization from React StrictMode
    if (initializationRef.current) {
      return;
    }

    initializationRef.current = true;

    // Clear any existing content to prevent duplicate rendering
    if (buttonRef.current) {
      buttonRef.current.innerHTML = '';
    }

    // Initialize Google Identity Services
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (response) => {
        try {
          await loginWithGoogle(response.credential);
        } catch (error) {
          console.error('Login error:', error);
        }
      },
    });

    // Render the sign-in button
    if (buttonRef.current) {
      window.google.accounts.id.renderButton(buttonRef.current, {
        theme: 'outline',
        size: 'large',
        text: 'signin_with',
      });
    }

    // Reset initialization flag on cleanup
    return () => {
      initializationRef.current = false;
    };
    // GOOGLE_CLIENT_ID is from import.meta.env and never changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isGoogleLoaded, loginWithGoogle]);

  // Check for missing client ID - render error if not configured
  if (!GOOGLE_CLIENT_ID) {
    return (
      <div className="google-signin-error">
        Google Sign-In is not configured. Please set VITE_GOOGLE_CLIENT_ID in your .env file.
      </div>
    );
  }

  if (sdkLoadError) {
    return (
      <div className="google-signin-error">
        Failed to load Google Sign-In. Please check your internet connection and ensure
        third-party scripts are not blocked.
      </div>
    );
  }

  if (!isGoogleLoaded) {
    return <div className="google-signin-loading">Loading sign-in button...</div>;
  }

  return <div ref={buttonRef} data-testid="google-signin-button"></div>;
}

import { render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LoggedInScreen } from '../src/components/LoggedInScreen';
import * as auth from '../src/lib/auth';
import type { User } from '../src/types/api';

// Mock the auth module
vi.mock('../src/lib/auth', async () => {
  const actual = await vi.importActual('../src/lib/auth');
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

describe('LoggedInScreen', () => {
  const mockLogout = vi.fn();
  const mockUseAuth = vi.mocked(auth.useAuth);

  const testUser: User = {
    userid: 'test-user-123',
    email: 'test@example.com',
    name: 'Test User',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      authState: { status: 'authenticated', user: testUser },
      loginWithGoogle: vi.fn(),
      logout: mockLogout,
    });
  });

  it('renders the heading', () => {
    render(<LoggedInScreen user={testUser} />);

    const heading = screen.getByRole('heading', {
      name: /genealogy detective desk/i,
    });
    expect(heading).toBeDefined();
  });

  it('displays user ID', () => {
    render(<LoggedInScreen user={testUser} />);

    expect(screen.getByText(/test-user-123/i)).toBeDefined();
  });

  it('displays user name when provided', () => {
    render(<LoggedInScreen user={testUser} />);

    expect(screen.getAllByText(/Test User/i).length).toBeGreaterThan(0);
  });

  it('displays user email when provided', () => {
    render(<LoggedInScreen user={testUser} />);

    expect(screen.getByText(/test@example.com/i)).toBeDefined();
  });

  it('does not display name field when name is null', () => {
    const userWithoutName: User = {
      ...testUser,
      name: null,
    };

    render(<LoggedInScreen user={userWithoutName} />);

    expect(screen.queryByText(/Name:/)).toBeNull();
  });

  it('does not display email field when email is null', () => {
    const userWithoutEmail: User = {
      ...testUser,
      email: null,
    };

    render(<LoggedInScreen user={userWithoutEmail} />);

    expect(screen.queryByText(/Email:/)).toBeNull();
  });

  it('renders logout button', () => {
    render(<LoggedInScreen user={testUser} />);

    const logoutButton = screen.getByRole('button', { name: /logout/i });
    expect(logoutButton).toBeDefined();
  });

  it('calls logout when logout button is clicked', async () => {
    const user = userEvent.setup();
    render(<LoggedInScreen user={testUser} />);

    const logoutButton = screen.getByRole('button', { name: /logout/i });
    await user.click(logoutButton);

    expect(mockLogout).toHaveBeenCalledOnce();
  });

  it('displays success message', () => {
    render(<LoggedInScreen user={testUser} />);

    expect(screen.getByText(/start with a gedcom, then work outward/i)).toBeDefined();
  });

  it('displays API endpoint reference', () => {
    render(<LoggedInScreen user={testUser} />);

    expect(screen.getByText(/clear existing data/i)).toBeDefined();
  });

  it('renders with minimal user data (only userid)', () => {
    const minimalUser: User = {
      userid: 'minimal-user',
      email: null,
      name: null,
    };

    render(<LoggedInScreen user={minimalUser} />);

    expect(screen.getAllByText(/minimal-user/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Name:/)).toBeNull();
    expect(screen.queryByText(/Email:/)).toBeNull();
  });
});

import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import App from '../src/App';

describe('App', () => {
  beforeEach(() => {
    render(<App />);
  });

  it('renders get started heading', () => {
    const heading = screen.getByRole('heading', {
      name: /get started/i,
    });
    expect(heading).toBeDefined();
  });

  it('renders documentation section', () => {
    const docsHeading = screen.getByRole('heading', {
      name: /documentation/i,
    });
    expect(docsHeading).toBeDefined();
  });

  it('renders connect with us section', () => {
    const socialHeading = screen.getByRole('heading', {
      name: /connect with us/i,
    });
    expect(socialHeading).toBeDefined();
  });

  it('displays counter button', () => {
    const button = screen.getByRole('button', {
      name: /count is 0/i,
    });
    expect(button).toBeDefined();
  });

  it('displays HMR message', () => {
    const hmrText = screen.getByText(/save to test/i);
    expect(hmrText).toBeDefined();
  });
});

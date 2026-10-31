import type { ComponentProps } from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { Navbar } from './Navbar';
import { getActiveRole } from '../api/client';

const FOUNDER = { principal_id: 'founder_live', role: 'FOUNDER' as const };

function renderNavbar(mode: 'live' | 'sample', overrides: Partial<ComponentProps<typeof Navbar>> = {}) {
  const props = {
    mode,
    principal: mode === 'live' ? FOUNDER : null,
    currentTab: 'customer' as const,
    onTabChange: vi.fn(),
    onSignOut: vi.fn(),
    onExitSample: vi.fn(),
    ...overrides,
  };
  render(<Navbar {...props} />);
  return props;
}

// At 375 and 768 px the header used to be one fixed-height row wider than the
// screen: the page scrolled sideways and controls left the screen.
describe('Navbar on a narrow screen', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('wraps its row instead of holding every control on one fixed-height line', () => {
    renderNavbar('sample');

    const row = screen.getByRole('banner').firstElementChild?.firstElementChild;
    expect(row).toHaveClass('flex-wrap');
    expect(row).not.toHaveClass('h-16');
    // Every control stays in that row, so wrapping keeps it on the screen.
    for (const name of [/Customer Portal/, /Founder Console/, /Exit sample data/]) {
      expect(row).toContainElement(screen.getByRole('button', { name }));
    }
  });
});

// 31 October 2026: signed in, the server's role decides the page, so the header
// has no page switch; it names the account and the test environment instead.
describe('Navbar when signed in', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('shows the signed-in account, the test environment and Sign out, with no page switch', () => {
    const props = renderNavbar('live');

    expect(screen.getByLabelText('Signed in as founder_live (Founder)')).toBeInTheDocument();
    expect(screen.getByText('Test environment')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Customer Portal/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Founder Console/ })).not.toBeInTheDocument();
    // No course badge, no developer switch.
    expect(screen.queryByText(/ELEC5620/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Mock Mode|Live API|Auth Tokens/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Sign out/ }));
    expect(props.onSignOut).toHaveBeenCalledTimes(1);
  });
});

describe('Navbar with the sample data', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('labels the sample data and switches the sample page and persona together', () => {
    const props = renderNavbar('sample');

    expect(screen.getByText('Sample data')).toBeInTheDocument();
    expect(screen.queryByText('Test environment')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Founder Console/ }));
    expect(props.onTabChange).toHaveBeenCalledWith('founder');
    expect(getActiveRole()).toBe('FOUNDER');

    fireEvent.click(screen.getByRole('button', { name: 'Exit sample data' }));
    expect(props.onExitSample).toHaveBeenCalledTimes(1);
  });
});

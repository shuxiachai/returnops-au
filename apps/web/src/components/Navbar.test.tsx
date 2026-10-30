import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Navbar } from './Navbar';

// At 375 and 768 px the header used to be one fixed-height row wider than the
// screen: the page scrolled sideways and Live API / Auth Tokens left the screen.
describe('Navbar on a narrow screen', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('wraps its row instead of holding every control on one fixed-height line', () => {
    render(<Navbar currentTab="customer" onTabChange={() => undefined} onOpenAuth={() => undefined} />);

    const row = screen.getByRole('banner').firstElementChild?.firstElementChild;
    expect(row).toHaveClass('flex-wrap');
    expect(row).not.toHaveClass('h-16');
    // Every control stays in that row, so wrapping keeps it on the screen.
    for (const name of [/Customer Portal/, /Founder Console/, /Mock Mode/, /Auth Tokens/]) {
      expect(row).toContainElement(screen.getByRole('button', { name }));
    }
  });
});

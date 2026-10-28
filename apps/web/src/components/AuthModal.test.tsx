import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AuthModal } from './AuthModal';
import { setMockMode } from '../api/client';

// #111 item 12: the demonstration is projected, so the bearer token is masked
// unless the operator asks to see it.
describe('AuthModal token field (#111 item 12)', () => {
  beforeEach(() => {
    localStorage.clear();
    setMockMode(true);
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('masks the token by default and shows it only on request', () => {
    render(<AuthModal isOpen onClose={() => undefined} />);
    const field = screen.getByLabelText('Bearer Token (JWT)') as HTMLInputElement;
    expect(field).toHaveAttribute('type', 'password');

    fireEvent.change(field, { target: { value: 'header.payload.signature' } });
    expect(field.value).toBe('header.payload.signature');

    const show = screen.getByRole('button', { name: 'Show token' });
    expect(show).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(show);
    expect(field).toHaveAttribute('type', 'text');

    const hide = screen.getByRole('button', { name: 'Hide token' });
    expect(hide).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(hide);
    expect(field).toHaveAttribute('type', 'password');
  });

  it('masks the token again when the dialog is reopened', () => {
    const view = render(<AuthModal isOpen onClose={() => undefined} />);
    fireEvent.click(screen.getByRole('button', { name: 'Show token' }));
    expect(screen.getByLabelText('Bearer Token (JWT)')).toHaveAttribute('type', 'text');

    view.rerender(<AuthModal isOpen={false} onClose={() => undefined} />);
    view.rerender(<AuthModal isOpen onClose={() => undefined} />);
    expect(screen.getByLabelText('Bearer Token (JWT)')).toHaveAttribute('type', 'password');
  });
});

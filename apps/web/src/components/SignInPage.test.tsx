import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SignInPage } from './SignInPage';
import { getStoredToken } from '../api/client';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function renderPage() {
  const onSignedIn = vi.fn();
  const onExploreSample = vi.fn();
  render(<SignInPage onSignedIn={onSignedIn} onExploreSample={onExploreSample} />);
  return { onSignedIn, onExploreSample };
}

describe('SignInPage (31 October 2026)', () => {
  beforeEach(() => localStorage.clear());

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // #111 item 12: the screen may be projected, so the key is masked unless asked.
  it('masks the access key by default and shows it only on request', () => {
    renderPage();
    const field = screen.getByLabelText('Access key') as HTMLInputElement;
    expect(field).toHaveAttribute('type', 'password');

    fireEvent.click(screen.getByRole('button', { name: 'Show access key' }));
    expect(field).toHaveAttribute('type', 'text');
    expect(screen.getByRole('button', { name: 'Hide access key' })).toHaveAttribute('aria-pressed', 'true');

    fireEvent.click(screen.getByRole('button', { name: 'Hide access key' }));
    expect(field).toHaveAttribute('type', 'password');
  });

  it('asks for a key instead of sending an empty one', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const { onSignedIn } = renderPage();

    fireEvent.change(screen.getByLabelText('Access key'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(screen.getByRole('alert')).toHaveTextContent('Enter your access key.');
    expect(fetchMock).not.toHaveBeenCalled();
    expect(onSignedIn).not.toHaveBeenCalled();
  });

  it('checks the trimmed key with the server and hands over the reported principal, saving nothing itself', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { principal_id: 'founder_live', role: 'FOUNDER', enabled: true, session_id: 's1' })
    );
    vi.stubGlobal('fetch', fetchMock);
    const { onSignedIn } = renderPage();

    fireEvent.change(screen.getByLabelText('Access key'), { target: { value: '  live.key  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await vi.waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
    expect(onSignedIn.mock.calls[0][0]).toMatchObject({ principal_id: 'founder_live', role: 'FOUNDER' });
    expect(onSignedIn.mock.calls[0][1]).toBe('live.key');
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(String(url)).toMatch(/\/v1\/session$/);
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer live.key');
    expect(getStoredToken()).toBe('');
  });

  it('says plainly when a key is refused or the service cannot be reached', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'The session is not valid.' } }))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetchMock);
    const { onSignedIn } = renderPage();

    fireEvent.change(screen.getByLabelText('Access key'), { target: { value: 'expired.key' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This access key was not accepted. It may have expired; ask for a new one.'
    );

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('The service is not reachable right now. Try again in a moment.')).toBeInTheDocument();
    expect(onSignedIn).not.toHaveBeenCalled();
    // No error code or host name reaches the screen.
    expect(screen.queryByText(/UNAUTHENTICATED|127\.0\.0\.1|Failed to fetch/)).not.toBeInTheDocument();
  });

  it('offers the sample data without a sign-in', () => {
    const { onExploreSample } = renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Explore with sample data' }));
    expect(onExploreSample).toHaveBeenCalledTimes(1);
  });
});

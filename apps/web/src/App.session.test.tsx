import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { App } from './App';
import { clearSessionRejection, getStoredToken, isMockMode, setActiveRole, setMockMode, setStoredToken } from './api/client';

// Sign-in and sessions (#111 item 1; 31 October 2026). Sessions last 15 minutes,
// so an ended session must be said on the page; and signed in, the role the server
// reports for the key decides the page, never a role stored in the browser.
const FOUNDER_KEY = 'founder.live.key';
const CUSTOMER_KEY = 'customer.live.key';
const EXPIRED_KEY = 'expired.live.key';
const SESSION_ENDED = 'Your session has ended. Sign in again to continue.';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const UNAUTHENTICATED = {
  error: { code: 'UNAUTHENTICATED', message: 'The session is not valid.', retryable: false },
};

// The server knows one Founder key and one customer key; with `endFounderSession`
// the Founder's session ends after /v1/session has accepted it.
function stubServer(options: { endFounderSession?: boolean } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const auth = new Headers(init?.headers).get('Authorization');
    const url = String(input);
    if (auth === `Bearer ${FOUNDER_KEY}`) {
      if (url.endsWith('/v1/session')) {
        return jsonResponse(200, { principal_id: 'founder_live', role: 'FOUNDER', enabled: true, session_id: 's_f' });
      }
      if (options.endFounderSession) return jsonResponse(401, UNAUTHENTICATED);
      if (url.includes('/v1/founder/cases')) return jsonResponse(200, { items: [] });
      return jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'Not found.' } });
    }
    if (auth === `Bearer ${CUSTOMER_KEY}` && url.endsWith('/v1/session')) {
      return jsonResponse(200, { principal_id: 'customer_live', role: 'CUSTOMER', enabled: true, session_id: 's_c' });
    }
    return jsonResponse(401, UNAUTHENTICATED);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('sign-in and sessions (#111 item 1; 31 October 2026)', () => {
  let alertSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.clear();
    clearSessionRejection();
    alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
  });

  afterEach(() => {
    // Nothing on these screens raises a browser alert.
    expect(alertSpy).not.toHaveBeenCalled();
    localStorage.clear();
    clearSessionRejection();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('opens the sign-in page on a first visit, with the sample data one click away', async () => {
    stubServer();
    render(<App />);

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.queryByRole('banner')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Explore with sample data' }));
    expect(isMockMode()).toBe(true);
    expect(screen.getByText('You are exploring built-in sample data. Nothing here is real or sent to the shop.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Founder Console/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Exit sample data' }));
    expect(isMockMode()).toBe(false);
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('signs a Founder in to the Founder Console only, with no page switch', async () => {
    stubServer();
    setMockMode(false);
    setActiveRole('CUSTOMER');
    render(<App />);

    fireEvent.change(screen.getByLabelText('Access key'), { target: { value: FOUNDER_KEY } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText('Founder Console & Governance')).toBeInTheDocument();
    expect(screen.getByLabelText('Signed in as founder_live (Founder)')).toBeInTheDocument();
    expect(getStoredToken()).toBe(FOUNDER_KEY);
    expect(screen.queryByRole('button', { name: /Customer Portal/ })).not.toBeInTheDocument();
    expect(screen.queryByText('Customer Service Portal')).not.toBeInTheDocument();
  });

  it('opens the page of the role the server reports for a saved key, not the role stored in the browser', async () => {
    stubServer();
    setMockMode(false);
    setStoredToken(CUSTOMER_KEY);
    setActiveRole('FOUNDER');
    render(<App />);

    expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();
    expect(screen.getByLabelText('Signed in as customer_live (Customer)')).toBeInTheDocument();
    expect(screen.queryByText('Founder Console & Governance')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Founder Console/ })).not.toBeInTheDocument();
  });

  it('returns an expired saved key to the sign-in page, says why, and forgets the key', async () => {
    stubServer();
    setMockMode(false);
    setStoredToken(EXPIRED_KEY);
    render(<App />);

    expect(await screen.findByText(SESSION_ENDED)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(getStoredToken()).toBe('');
  });

  it('shows one banner when the session ends on an open page, then signs in again from it', async () => {
    stubServer({ endFounderSession: true });
    setMockMode(false);
    setStoredToken(FOUNDER_KEY);
    render(<App />);

    // The queue read is refused after the session check passed; the page stays,
    // with the banner above it.
    expect(await screen.findByText(SESSION_ENDED)).toBeInTheDocument();
    expect(screen.getByText('Founder Console & Governance')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Sign in again' }));
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.getByText(SESSION_ENDED)).toBeInTheDocument();
    expect(getStoredToken()).toBe('');
  });

  it('signs out to the sign-in page and forgets the key', async () => {
    stubServer();
    setMockMode(false);
    setStoredToken(FOUNDER_KEY);
    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: /Sign out/ }));
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.queryByText(SESSION_ENDED)).not.toBeInTheDocument();
    expect(getStoredToken()).toBe('');
  });

  it('keeps a saved key when the service cannot be reached, and tries again on request', async () => {
    const fetchMock = stubServer();
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    setMockMode(false);
    setStoredToken(FOUNDER_KEY);
    render(<App />);

    expect(await screen.findByText('The service is not reachable right now')).toBeInTheDocument();
    expect(getStoredToken()).toBe(FOUNDER_KEY);

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.getByText('Founder Console & Governance')).toBeInTheDocument());
  });
});

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { App } from './App';
import { clearSessionRejection, getStoredToken, setActiveRole, setMockMode, setStoredToken } from './api/client';

// #111 item 1 (FR-012, NFR-006): demo sessions last 15 minutes, so an expired
// token must be visible on the page, in the header and in the Auth Tokens dialog.
const FRESH_TOKEN = 'fresh.demo.token';
const EXPIRED_TOKEN = 'expired.demo.token';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

const UNAUTHENTICATED = {
  error: { code: 'UNAUTHENTICATED', message: 'The session is not valid.', retryable: false },
};

// The server accepts only the fresh token; /v1/session reports its principal.
function stubServer() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const auth = new Headers(init?.headers).get('Authorization');
    const url = String(input);
    if (auth !== `Bearer ${FRESH_TOKEN}`) return jsonResponse(401, UNAUTHENTICATED);
    if (url.endsWith('/v1/session')) {
      return jsonResponse(200, { principal_id: 'founder_live', role: 'FOUNDER', enabled: true, session_id: 'session_live' });
    }
    if (url.includes('/v1/founder/cases')) return jsonResponse(200, { items: [] });
    return jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'Not found.' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('session expiry in Live API mode (#111 item 1)', () => {
  beforeEach(() => {
    localStorage.clear();
    clearSessionRejection();
    setMockMode(false);
  });

  afterEach(() => {
    localStorage.clear();
    clearSessionRejection();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('shows one on-page banner and a signed-out header badge on a 401, with no browser alert', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    stubServer();
    setStoredToken(EXPIRED_TOKEN);
    setActiveRole('FOUNDER');

    render(<App />);

    expect(
      await screen.findByText('Session expired or not valid. Open Auth Tokens and paste a new token.')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Auth Tokens: Signed out' })).toBeInTheDocument();
    // The stored persona is not shown as if the token were still valid.
    expect(screen.queryByRole('button', { name: /Auth Tokens: FOUNDER/ })).not.toBeInTheDocument();
    // The queue reports the refusal on the page as well.
    expect(await screen.findByText('[UNAUTHENTICATED] The session is not valid.')).toBeInTheDocument();
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it('verifies the pasted token, not the saved one, and saves nothing until Save & Apply', async () => {
    const fetchMock = stubServer();
    setStoredToken(EXPIRED_TOKEN);
    setActiveRole('CUSTOMER');

    render(<App />);
    fireEvent.click(await screen.findByRole('button', { name: 'Open Auth Tokens' }));

    // On opening, the saved token is checked and refused.
    expect(
      await screen.findByText('This token was refused: it has expired or is not valid. Paste a new token from sessions.json.')
    ).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/Paste JWT issued by returnops_api.demo provision/i), {
      target: { value: `  ${FRESH_TOKEN}  ` },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

    const valid = await screen.findByText('founder_live');
    expect(valid.closest('span')).toHaveTextContent('Valid: founder_live (FOUNDER)');
    // The check sent the pasted text (trimmed) to /v1/session.
    const sessionCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/v1/session'));
    const lastAuth = new Headers(sessionCalls[sessionCalls.length - 1][1]?.headers).get('Authorization');
    expect(lastAuth).toBe(`Bearer ${FRESH_TOKEN}`);
    // Nothing was saved, and the persona now follows the role the server reported.
    expect(getStoredToken()).toBe(EXPIRED_TOKEN);
    const founderPersona = screen.getByText('Founder (Merchant)').closest('button');
    expect(founderPersona?.className).toMatch(/border-sky-500/);
    // A refused check of a pasted token does not change the page's session state.
    expect(screen.getByText('Session expired or not valid. Open Auth Tokens and paste a new token.')).toBeInTheDocument();
  });

  it('shows the principal and role from /v1/session, not the persona saved in the browser', async () => {
    stubServer();
    setStoredToken(FRESH_TOKEN);
    setActiveRole('CUSTOMER');

    render(<App />);

    const badge = await screen.findByRole('button', { name: 'Auth Tokens: FOUNDER · founder_live' });
    expect(within(badge).getByText('FOUNDER · founder_live')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });
});

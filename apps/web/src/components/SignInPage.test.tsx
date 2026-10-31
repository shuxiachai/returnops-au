import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { SignInPage } from './SignInPage';
import { getStoredToken } from '../api/client';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function refusal(status: number, code: string, message: string): Response {
  return jsonResponse(status, { error: { code, message, correlation_id: 'corr_test', retryable: false, details: [] } });
}

const FOUNDER = { principal_id: 'founder_live', role: 'FOUNDER', enabled: true, session_id: 's1' };
const NEW_CUSTOMER = { principal_id: 'new_customer', role: 'CUSTOMER', enabled: true, session_id: 's2' };

function passwordSession(principal: { principal_id: string; role: string }, token: string) {
  return jsonResponse(200, { access_token: token, token_type: 'Bearer', expires_in: 899, ...principal });
}

function renderPage() {
  const onSignedIn = vi.fn();
  const onExploreSample = vi.fn();
  render(<SignInPage onSignedIn={onSignedIn} onExploreSample={onExploreSample} />);
  return { onSignedIn, onExploreSample };
}

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function call(fetchMock: ReturnType<typeof vi.fn>, index: number) {
  const [url, init] = fetchMock.mock.calls[index] as unknown as [string, RequestInit];
  return { url: String(url), init, headers: new Headers(init.headers) };
}

// 31 October 2026: password sign-in and customer self-registration, with the access key
// kept as the fallback. Every route checks with the server before anything is saved.
describe('SignInPage', () => {
  beforeEach(() => localStorage.clear());

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  // #111 item 12: the screen may be projected, so secrets are masked unless asked.
  it('masks the password by default and shows it only on request', () => {
    renderPage();
    const field = screen.getByLabelText('Password') as HTMLInputElement;
    expect(field).toHaveAttribute('type', 'password');
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(field).toHaveAttribute('type', 'text');
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(field).toHaveAttribute('type', 'password');
  });

  it('signs in with a username and password, then checks the new session before handing it over', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(passwordSession(FOUNDER, 'new.founder.token')).mockResolvedValueOnce(jsonResponse(200, FOUNDER));
    vi.stubGlobal('fetch', fetchMock);
    localStorage.setItem('returnops_auth_token', 'old.saved.token');
    const { onSignedIn } = renderPage();

    fill('Username', '  founder_live  ');
    fill('Password', 'founder-pass-1234');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await vi.waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
    expect(onSignedIn.mock.calls[0][0]).toMatchObject({ principal_id: 'founder_live', role: 'FOUNDER' });
    expect(onSignedIn.mock.calls[0][1]).toBe('new.founder.token');
    const login = call(fetchMock, 0);
    expect(login.url).toMatch(/\/v1\/auth\/login$/);
    expect(JSON.parse(String(login.init.body))).toEqual({ username: 'founder_live', password: 'founder-pass-1234' });
    // The old saved token is not sent with a sign-in.
    expect(login.headers.get('Authorization')).toBe('');
    expect(call(fetchMock, 1).headers.get('Authorization')).toBe('Bearer new.founder.token');
    expect(getStoredToken()).toBe('old.saved.token');
  });

  it("shows the server's sentence for a wrong password and names a server without password sign-in", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(refusal(401, 'UNAUTHENTICATED', 'The username or password is not correct.'))
      .mockResolvedValueOnce(new Response('', { status: 404 }))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetchMock);
    const { onSignedIn } = renderPage();

    fill('Username', 'founder_live');
    fill('Password', 'wrong-password');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('The username or password is not correct.');

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Password sign-in is not available on this server. Use an access key instead.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('The service is not reachable right now. Try again in a moment.')).toBeInTheDocument();
    expect(onSignedIn).not.toHaveBeenCalled();
    expect(screen.queryByText(/UNAUTHENTICATED|Failed to fetch|HTTP_404/)).not.toBeInTheDocument();
  });

  it('creates a customer account after checking the two passwords, and shows a taken username', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(refusal(409, 'INVALID_STATE', 'That username is already taken. Choose another one.'))
      .mockResolvedValueOnce(jsonResponse(201, { access_token: 'new.customer.token', token_type: 'Bearer', expires_in: 899, ...NEW_CUSTOMER }))
      .mockResolvedValueOnce(jsonResponse(200, NEW_CUSTOMER));
    vi.stubGlobal('fetch', fetchMock);
    const { onSignedIn } = renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'Create an account' }));
    expect(screen.getByRole('heading', { name: 'Create a customer account' })).toBeInTheDocument();
    fill('Username', 'new_customer');
    fill('Password', 'short');
    fill('Confirm password', 'short');
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Choose a password of 8 to 128 characters.');
    fill('Password', 'a-long-password');
    fill('Confirm password', 'a-long-passw0rd');
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByRole('alert')).toHaveTextContent('The two passwords do not match.');
    expect(fetchMock).not.toHaveBeenCalled();

    fill('Confirm password', 'a-long-password');
    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('That username is already taken. Choose another one.');

    fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
    await vi.waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
    expect(call(fetchMock, 1).url).toMatch(/\/v1\/auth\/register$/);
    expect(onSignedIn.mock.calls[0][0]).toMatchObject({ principal_id: 'new_customer', role: 'CUSTOMER' });
    expect(onSignedIn.mock.calls[0][1]).toBe('new.customer.token');
  });

  it('keeps the access key as a fallback: masked, checked with the server, refusals in plain words', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(refusal(401, 'UNAUTHENTICATED', 'A valid session is required.'))
      .mockResolvedValueOnce(jsonResponse(200, FOUNDER));
    vi.stubGlobal('fetch', fetchMock);
    const { onSignedIn } = renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'Use an access key instead' }));
    const field = screen.getByLabelText('Access key') as HTMLInputElement;
    expect(field).toHaveAttribute('type', 'password');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your access key.');
    expect(fetchMock).not.toHaveBeenCalled();

    fill('Access key', '  expired.key  ');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This access key was not accepted. It may have expired; ask for a new one.'
    );

    fill('Access key', '  live.key  ');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await vi.waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
    expect(call(fetchMock, 1).headers.get('Authorization')).toBe('Bearer live.key');
    expect(onSignedIn.mock.calls[0][1]).toBe('live.key');

    fireEvent.click(screen.getByRole('button', { name: 'Sign in with a username and password' }));
    expect(screen.getByLabelText('Username')).toBeInTheDocument();
  });

  it('offers the sample data without a sign-in', () => {
    const { onExploreSample } = renderPage();
    fireEvent.click(screen.getByRole('button', { name: 'Explore with sample data' }));
    expect(onExploreSample).toHaveBeenCalledTimes(1);
  });
});

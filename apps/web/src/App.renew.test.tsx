import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { App } from './App';
import {
  clearSessionRejection,
  getStoredToken,
  setMockMode,
  setStoredToken,
  SHARED_STORAGE_KEYS,
  tokenExpiry,
  tokenSubject,
} from './api/client';

// A password sign-in stays signed in for an hour (1 November 2026): each key still lasts at
// most 15 minutes, so from 280 s before it ends the page asks for the next one and, after a
// failure that may pass, tries again every 25 s; a refusal for good stops it.
function key(name: string, exp: number): string {
  const encode = (value: object) =>
    btoa(JSON.stringify(value)).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ sub: name, exp })}.not-a-signature`;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function signedIn(token: string) {
  return jsonResponse(200, { access_token: token, token_type: 'Bearer', expires_in: 899, principal_id: 'customer_live', role: 'CUSTOMER' });
}

function refusal(status: number, retryable: boolean, message = 'This sign-in cannot be renewed. Sign in again.') {
  return jsonResponse(status, { error: { code: status === 409 ? 'INVALID_STATE' : 'NOT_FOUND', message, retryable } });
}

const SESSION_ENDED = 'Your session has ended. Sign in again to continue.';

// The customer's server; `renew` answers the n-th renewal (0-based); `queue` answers the
// Founder's queue reads when the role is FOUNDER.
function stubServer(
  renew: (attempt: number, auth: string) => Response,
  options: { role?: 'CUSTOMER' | 'FOUNDER'; queue?: (read: number) => Response } = {}
) {
  const renewals: string[] = [];
  let queueReads = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const auth = new Headers(init?.headers).get('Authorization') || '';
      if (url.endsWith('/v1/auth/renew')) {
        renewals.push(auth);
        return renew(renewals.length - 1, auth);
      }
      if (url.endsWith('/v1/session')) {
        const role = options.role ?? 'CUSTOMER';
        return jsonResponse(200, { principal_id: 'customer_live', role, enabled: true, session_id: 's_c' });
      }
      if (url.includes('/v1/founder/cases') && options.queue) return options.queue(queueReads++);
      if (url.includes('/v1/cases')) return jsonResponse(200, { items: [], limit: 20 });
      return jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'Not found.', retryable: false } });
    })
  );
  return renewals;
}

async function pass(milliseconds: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(milliseconds);
  });
}

describe('one-hour password sign-in (1 November 2026)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    localStorage.clear();
    clearSessionRejection();
    setMockMode(false);
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
    clearSessionRejection();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('reads when a key ends and whose it is from its claims, and nothing from anything else', () => {
    expect(tokenExpiry(key('customer_live', 1793500000))).toBe(1793500000);
    expect(tokenSubject(key('customer_live', 1793500000))).toBe('customer_live');
    expect(tokenExpiry('customer.live.key')).toBeNull();
    expect(tokenSubject('')).toBeNull();
  });

  it('asks for the next key from 280 s before the current one ends, then for the one after', async () => {
    const now = Math.floor(Date.now() / 1000);
    const first = key('customer_live', now + 290);
    const second = key('customer_live', now + 1190);
    const third = key('customer_live', now + 2090);
    const renewals = stubServer((_, auth) => signedIn(auth === `Bearer ${first}` ? second : third));
    setStoredToken(first);
    render(<App />);
    expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();

    await pass(8_000);
    expect(renewals).toEqual([]);
    await pass(3_000);
    expect(renewals).toEqual([`Bearer ${first}`]);
    expect(getStoredToken()).toBe(second);

    await pass(900_000);
    expect(renewals).toEqual([`Bearer ${first}`, `Bearer ${second}`]);
    expect(getStoredToken()).toBe(third);
    expect(screen.getByText('Customer Service Portal')).toBeInTheDocument();
  });

  it('tries again every 25 s after a failure that may pass, such as another API during S5', async () => {
    const now = Math.floor(Date.now() / 1000);
    const first = key('customer_live', now + 200);
    const second = key('customer_live', now + 1100);
    const renewals = stubServer((attempt) =>
      attempt === 0
        ? refusal(404, false, 'Not found.')
        : attempt === 1
          ? refusal(409, true, 'This key is renewed in its last five minutes.')
          : signedIn(second)
    );
    setStoredToken(first);
    render(<App />);
    expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();

    await pass(2_000);
    expect(renewals.length).toBe(1);
    await pass(25_000);
    expect(renewals.length).toBe(2);
    expect(getStoredToken()).toBe(first);
    await pass(25_000);
    expect(renewals.length).toBe(3);
    expect(getStoredToken()).toBe(second);
  });

  it('stops after a refusal for good or a key that is no longer valid, and keeps the key', async () => {
    for (const answer of [refusal(409, false), refusal(401, false, 'The session is not valid.')]) {
      const now = Math.floor(Date.now() / 1000);
      const only = key('customer_live', now + 130);
      const renewals = stubServer(() => answer.clone());
      setStoredToken(only);
      const view = render(<App />);
      expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();

      await pass(100_000);
      expect(renewals).toEqual([`Bearer ${only}`]);
      expect(getStoredToken()).toBe(only);
      // The refusal is not a rejected session: no banner while the key still works.
      expect(screen.queryByText(SESSION_ENDED)).not.toBeInTheDocument();
      view.unmount();
      vi.unstubAllGlobals();
    }
  });

  it('keeps the key when the next one would end no later, and asks no more', async () => {
    const now = Math.floor(Date.now() / 1000);
    const only = key('customer_live', now + 100);
    const renewals = stubServer(() => signedIn(key('customer_live', now + 100)));
    setStoredToken(only);
    render(<App />);
    expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();
    await pass(90_000);
    expect(renewals.length).toBe(1);
    expect(getStoredToken()).toBe(only);
  });

  it("follows the same person's key from another tab without reloading the page", async () => {
    const now = Math.floor(Date.now() / 1000);
    const first = key('customer_live', now + 500);
    const fromOtherTab = key('customer_live', now + 1300);
    const renewals = stubServer((_, auth) => signedIn(auth === `Bearer ${fromOtherTab}` ? key('customer_live', now + 2200) : fromOtherTab));
    setStoredToken(first);
    render(<App />);
    expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();

    // The other tab renewed: the key changes in storage and a storage event arrives.
    localStorage.setItem(SHARED_STORAGE_KEYS.token, fromOtherTab);
    await act(async () => {
      window.dispatchEvent(new StorageEvent('storage', { key: SHARED_STORAGE_KEYS.token }));
    });
    expect(screen.queryByText('Signing you in...')).not.toBeInTheDocument();
    expect(screen.getByText('Customer Service Portal')).toBeInTheDocument();

    // This tab's own timer was for the old key; the next renewal uses the other tab's key.
    await pass(1_100_000);
    expect(renewals[0]).toBe(`Bearer ${fromOtherTab}`);
  });

  it('takes down the "session has ended" banner once a renewal succeeds', async () => {
    const now = Math.floor(Date.now() / 1000);
    const first = key('customer_live', now + 200);
    stubServer(() => signedIn(key('customer_live', now + 1100)), {
      role: 'FOUNDER',
      queue: (read) => (read === 0 ? refusal(401, false, 'The session is not valid.') : jsonResponse(200, { items: [] })),
    });
    setStoredToken(first);
    render(<App />);
    expect(await screen.findByText(SESSION_ENDED)).toBeInTheDocument();
    await pass(2_000);
    expect(screen.queryByText(SESSION_ENDED)).not.toBeInTheDocument();
  });

  it('does not renew a saved key that is not a readable token', async () => {
    const renewals = stubServer(() => jsonResponse(500, {}));
    setStoredToken('customer.live.key');
    render(<App />);
    expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();
    await pass(1_000_000);
    expect(renewals).toEqual([]);
  });
});

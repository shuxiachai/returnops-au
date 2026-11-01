import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { App } from './App';
import { clearSessionRejection, getStoredToken, setMockMode, setStoredToken, tokenExpiry } from './api/client';

// A password sign-in stays signed in for an hour (1 November 2026): each key still lasts
// at most 15 minutes, so two minutes before it ends the page asks for the next one, and a
// refusal leaves the key to end as before.
function key(name: string, exp: number): string {
  const encode = (value: object) =>
    btoa(JSON.stringify(value)).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ sub: name, exp })}.not-a-signature`;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

// The customer's server; `renew` answers each renewal.
function stubServer(renew: (auth: string) => Response) {
  const renewals: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const auth = new Headers(init?.headers).get('Authorization') || '';
      if (url.endsWith('/v1/auth/renew')) {
        renewals.push(auth);
        return renew(auth);
      }
      if (url.endsWith('/v1/session')) {
        return jsonResponse(200, { principal_id: 'customer_live', role: 'CUSTOMER', enabled: true, session_id: 's_c' });
      }
      if (url.includes('/v1/cases')) return jsonResponse(200, { items: [], limit: 20 });
      return jsonResponse(404, { error: { code: 'NOT_FOUND', message: 'Not found.', retryable: false } });
    })
  );
  return renewals;
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

  it('reads when a key ends from its claims, and nothing from anything else', () => {
    expect(tokenExpiry(key('customer_live', 1793500000))).toBe(1793500000);
    expect(tokenExpiry('customer.live.key')).toBeNull();
    expect(tokenExpiry('')).toBeNull();
  });

  it('asks for the next key two minutes before the current one ends, then for the one after', async () => {
    const now = Math.floor(Date.now() / 1000);
    const first = key('customer_live', now + 130);
    const second = key('customer_live', now + 1030);
    const third = key('customer_live', now + 1900);
    const renewals = stubServer((auth) =>
      jsonResponse(200, {
        access_token: auth === `Bearer ${first}` ? second : third,
        token_type: 'Bearer',
        expires_in: 899,
        principal_id: 'customer_live',
        role: 'CUSTOMER',
      })
    );
    setStoredToken(first);
    render(<App />);
    expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(renewals).toEqual([]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6_000);
    });
    expect(renewals).toEqual([`Bearer ${first}`]);
    expect(getStoredToken()).toBe(second);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(900_000);
    });
    expect(renewals).toEqual([`Bearer ${first}`, `Bearer ${second}`]);
    expect(getStoredToken()).toBe(third);
    expect(screen.getByText('Customer Service Portal')).toBeInTheDocument();
  });

  it('keeps the key as it is when the server refuses, and asks no more for that key', async () => {
    const now = Math.floor(Date.now() / 1000);
    const only = key('customer_live', now + 130);
    const renewals = stubServer(() =>
      jsonResponse(409, {
        error: { code: 'INVALID_STATE', message: 'This sign-in cannot be renewed. Sign in again.', retryable: false },
      })
    );
    setStoredToken(only);
    render(<App />);
    expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(renewals).toEqual([`Bearer ${only}`]);
    expect(getStoredToken()).toBe(only);
    // The refusal is not a rejected session: no banner while the key still works.
    expect(screen.queryByText('Your session has ended. Sign in again to continue.')).not.toBeInTheDocument();
  });

  it('does not renew a saved key that is not a readable token', async () => {
    const renewals = stubServer(() => jsonResponse(500, {}));
    setStoredToken('customer.live.key');
    render(<App />);
    expect(await screen.findByText('Customer Service Portal')).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000_000);
    });
    expect(renewals).toEqual([]);
  });
});

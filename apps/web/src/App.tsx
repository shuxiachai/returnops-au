import React, { useEffect, useRef, useState } from 'react';
import { Database, RefreshCw, WifiOff } from 'lucide-react';
import { Navbar } from './components/Navbar';
import { CustomerPortal } from './pages/CustomerPortal';
import { FounderConsole } from './pages/FounderConsole';
import { SessionBanner } from './components/SessionBanner';
import { SignInPage } from './components/SignInPage';
import { SiteFooter } from './components/SiteFooter';
import {
  ApiError,
  clearSessionRejection,
  getActiveRole,
  getSession,
  getStoredToken,
  renewPasswordSession,
  sampleDataChosen,
  SHARED_STORAGE_KEYS,
  setActiveRole,
  setMockMode,
  setStoredToken,
  tokenExpiry,
  tokenSubject,
} from './api/client';
import { SessionPrincipal } from './types/domain';

// What the app shows (31 October 2026). Signed in, the role the server reports for
// the saved key decides the page; only the sample data lets the user switch pages.
type Gate =
  | { kind: 'checking' }
  | { kind: 'signed-out'; notice?: string }
  | { kind: 'unreachable' }
  | { kind: 'signed-in'; principal: SessionPrincipal }
  | { kind: 'sample' };

const SESSION_ENDED = 'Your session has ended. Sign in again to continue.';
const CHANGED_ELSEWHERE = 'You signed in, signed out or opened the sample data in another tab. Sign in again here.';
// The next key of a password sign-in is asked for from this long before the current one
// ends (the server renews in a key's last 300 s), and again this often after a failure.
const RENEW_START_SECONDS = 280;
const RENEW_RETRY_SECONDS = 25;

// Whether a failed renewal is tried again: not after a refusal for good. The server marks
// "too early" as retryable; "cannot be renewed" and "the hour has passed" are not.
function renewalWorthRetrying(err: unknown): boolean {
  if (!(err instanceof ApiError)) return true;
  if (err.status === 401 || err.status === 403) return false;
  if (err.status === 409) return err.retryable === true;
  return true;
}

function startingGate(): Gate {
  if (sampleDataChosen()) return { kind: 'sample' };
  // Outside the sample data every request goes to the server, also on a first visit.
  setMockMode(false);
  return getStoredToken() ? { kind: 'checking' } : { kind: 'signed-out' };
}

export const App: React.FC = () => {
  const [gate, setGate] = useState<Gate>(startingGate);
  const [sampleTab, setSampleTab] = useState<'customer' | 'founder'>(
    getActiveRole() === 'FOUNDER' ? 'founder' : 'customer'
  );
  const [renewals, setRenewals] = useState(0);
  // The gate as last shown, for the storage listener, which is set up once.
  const gateRef = useRef(gate);
  gateRef.current = gate;

  // A saved key is checked with the server before any page opens.
  useEffect(() => {
    if (gate.kind !== 'checking') return;
    let cancelled = false;
    getSession()
      .then((principal) => {
        if (cancelled) return;
        setActiveRole(principal.role);
        setGate({ kind: 'signed-in', principal });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          setStoredToken('');
          clearSessionRejection();
          setGate({ kind: 'signed-out', notice: SESSION_ENDED });
        } else {
          setGate({ kind: 'unreachable' });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [gate.kind]);

  // The token and the sample-data choice are shared by every tab of this browser, so a
  // change made in another tab would otherwise send this tab's requests with someone
  // else's session or mode (runtime review, 31 October 2026). This tab follows the change.
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      const { token, sampleData } = SHARED_STORAGE_KEYS;
      if (event.key !== null && event.key !== token && event.key !== sampleData) return;
      // The same person's next key (a renewal or a new sign-in in another tab) keeps this
      // page as it is, open case and typed text included; it only times the next renewal.
      const shown = gateRef.current;
      const stored = getStoredToken();
      if (event.key === token && shown.kind === 'signed-in' && !sampleDataChosen() && stored &&
          tokenSubject(stored) === shown.principal.principal_id) {
        clearSessionRejection();
        setRenewals((count) => count + 1);
        return;
      }
      setGate((current) => {
        const sample = sampleDataChosen();
        if (event.key === sampleData && sample === (current.kind === 'sample')) return current;
        clearSessionRejection();
        if (sample) return { kind: 'sample' };
        return getStoredToken() ? { kind: 'checking' } : { kind: 'signed-out', notice: CHANGED_ELSEWHERE };
      });
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // A password sign-in stays signed in for an hour (1 November 2026). Each key lasts at most
  // 15 minutes; from RENEW_START_SECONDS before it ends this tab asks for the next one, and
  // after a failure (no answer, a busy server, an address that shows another API while S5
  // runs, a clock a little ahead) tries again every RENEW_RETRY_SECONDS until the key ends.
  // A refusal for good (an access key, the hour has passed, a key no longer valid) stops it.
  useEffect(() => {
    if (gate.kind !== 'signed-in') return;
    const token = getStoredToken();
    const ends = tokenExpiry(token);
    if (ends === null) return;
    let cancelled = false;
    let timer = 0;
    const attempt = () => {
      if (cancelled) return;
      // Another tab renewed meanwhile: follow its key instead of asking twice.
      if (getStoredToken() !== token) {
        setRenewals((count) => count + 1);
        return;
      }
      renewPasswordSession(token)
        .then((next) => {
          if (cancelled || getStoredToken() !== token) return;
          const nextEnds = tokenExpiry(next.access_token);
          if (nextEnds === null || nextEnds <= ends) return;
          setStoredToken(next.access_token);
          // The key works again, so an earlier refusal (seen while S5 ran) no longer holds.
          clearSessionRejection();
          setRenewals((count) => count + 1);
        })
        .catch((err: unknown) => {
          if (cancelled || !renewalWorthRetrying(err)) return;
          if (Date.now() / 1000 + RENEW_RETRY_SECONDS < ends) {
            timer = window.setTimeout(attempt, RENEW_RETRY_SECONDS * 1000);
          }
        });
    };
    timer = window.setTimeout(attempt, Math.max(1, ends - RENEW_START_SECONDS - Date.now() / 1000) * 1000);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [gate, renewals]);

  const signOut = (notice?: string) => {
    setStoredToken('');
    clearSessionRejection();
    setGate({ kind: 'signed-out', notice });
  };

  const handleSignedIn = (principal: SessionPrincipal, accessKey: string) => {
    setStoredToken(accessKey);
    setMockMode(false);
    setActiveRole(principal.role);
    clearSessionRejection();
    setGate({ kind: 'signed-in', principal });
  };

  const exploreSample = () => {
    setMockMode(true);
    setActiveRole('CUSTOMER');
    setSampleTab('customer');
    setGate({ kind: 'sample' });
  };

  const exitSample = () => {
    setMockMode(false);
    setGate(startingGate());
  };

  if (gate.kind === 'signed-out') {
    return <SignInPage notice={gate.notice} onSignedIn={handleSignedIn} onExploreSample={exploreSample} />;
  }

  if (gate.kind === 'checking' || gate.kind === 'unreachable') {
    return (
      <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
        <main className="flex-1 flex items-center justify-center px-4 py-12">
          {gate.kind === 'checking' ? (
            <p role="status" className="flex items-center gap-2 text-sm text-slate-500">
              <RefreshCw className="w-4 h-4 animate-spin" />
              <span>Signing you in...</span>
            </p>
          ) : (
            <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-sm p-6 text-center">
              <WifiOff className="w-6 h-6 text-slate-400 mx-auto" />
              <h1 className="mt-3 text-base font-semibold text-slate-900">The service is not reachable right now</h1>
              <p className="mt-1 text-sm text-slate-500">Your sign-in is kept. Try again in a moment.</p>
              <div className="mt-5 flex justify-center gap-3">
                <button
                  type="button"
                  onClick={() => setGate({ kind: 'checking' })}
                  className="px-4 py-2 text-sm font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-xl"
                >
                  Try again
                </button>
                <button
                  type="button"
                  onClick={() => signOut()}
                  className="px-4 py-2 text-sm font-medium text-slate-700 border border-slate-300 hover:bg-slate-100 rounded-xl"
                >
                  Sign out
                </button>
              </div>
            </div>
          )}
        </main>
        <SiteFooter />
      </div>
    );
  }

  const sample = gate.kind === 'sample';
  const page = sample ? sampleTab : gate.principal.role === 'FOUNDER' ? 'founder' : 'customer';

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      <Navbar
        mode={sample ? 'sample' : 'live'}
        principal={sample ? null : gate.principal}
        currentTab={page}
        onTabChange={setSampleTab}
        onSignOut={() => signOut()}
        onExitSample={exitSample}
      />
      {sample ? (
        <div role="note" className="bg-amber-50 border-b border-amber-200 text-amber-900 text-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 flex items-center gap-2">
            <Database className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>You are exploring built-in sample data. Nothing here is real or sent to the shop.</span>
          </div>
        </div>
      ) : (
        <SessionBanner onSignInAgain={() => signOut(SESSION_ENDED)} />
      )}

      <main className="flex-1 pb-16">{page === 'customer' ? <CustomerPortal /> : <FounderConsole />}</main>

      <SiteFooter />
    </div>
  );
};
export default App;

import React, { useEffect, useState } from 'react';
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
  sampleDataChosen,
  setActiveRole,
  setMockMode,
  setStoredToken,
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

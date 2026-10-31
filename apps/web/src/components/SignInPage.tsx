import React, { useState } from 'react';
import { AlertCircle, Info, LogIn, RefreshCw, RotateCcw } from 'lucide-react';
import { ApiError, NETWORK_ERROR, verifySessionToken } from '../api/client';
import { SessionPrincipal } from '../types/domain';
import { SiteFooter } from './SiteFooter';

interface SignInPageProps {
  // Why the page is shown again, for example an ended session.
  notice?: string;
  onSignedIn: (principal: SessionPrincipal, accessKey: string) => void;
  onExploreSample: () => void;
}

function signInError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401 || err.status === 403) {
      return 'This access key was not accepted. It may have expired; ask for a new one.';
    }
    if (err.code === NETWORK_ERROR || err.status >= 500) {
      return 'The service is not reachable right now. Try again in a moment.';
    }
    return err.message;
  }
  return 'Signing in failed. Try again in a moment.';
}

// The first screen (31 October 2026), in place of the Auth Tokens dialog. The key
// is checked with GET /v1/session before anything is saved, and the role the
// server reports decides which page opens; the browser never picks a role itself.
export const SignInPage: React.FC<SignInPageProps> = ({ notice, onSignedIn, onExploreSample }) => {
  const [accessKey, setAccessKey] = useState('');
  // Masked unless asked: the key is a credential while its session lasts, and the
  // screen may be projected (#111 item 12).
  const [showKey, setShowKey] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const candidate = accessKey.trim();
    if (!candidate) {
      setError('Enter your access key.');
      return;
    }
    setChecking(true);
    setError('');
    try {
      const principal = await verifySessionToken(candidate);
      onSignedIn(principal, candidate);
    } catch (err: unknown) {
      setError(signInError(err));
      setChecking(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="bg-sky-600 text-white p-2 rounded-xl shadow-md flex items-center justify-center">
              <RotateCcw className="w-6 h-6" />
            </div>
            <div>
              <div className="font-bold text-xl text-slate-900 tracking-tight">ReturnOps AU</div>
              <div className="text-xs text-slate-500">Returns assistant for a small Australian online shop</div>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-6 sm:p-8">
            <h1 className="text-lg font-semibold text-slate-900">Sign in</h1>
            <p className="text-sm text-slate-500 mt-1">
              Customers see their own returns; the shop's Founder sees the review console. Your access key decides which.
            </p>

            {notice && (
              <div
                role="status"
                className="mt-4 flex items-start gap-2 text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
              >
                <Info className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-600" />
                <span>{notice}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="mt-5 space-y-4" noValidate>
              <div>
                <label htmlFor="access-key" className="block text-sm font-medium text-slate-700 mb-1.5">
                  Access key
                </label>
                <div className="flex items-stretch gap-2">
                  <input
                    id="access-key"
                    type={showKey ? 'text' : 'password'}
                    value={accessKey}
                    onChange={(e) => {
                      setAccessKey(e.target.value);
                      setError('');
                    }}
                    autoComplete="off"
                    spellCheck={false}
                    aria-describedby="access-key-help"
                    aria-invalid={error ? true : undefined}
                    className="w-full min-w-0 text-sm font-mono px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey((shown) => !shown)}
                    aria-pressed={showKey}
                    aria-label={showKey ? 'Hide access key' : 'Show access key'}
                    className="px-3 text-xs font-medium text-slate-600 border border-slate-300 rounded-xl hover:bg-slate-100 shrink-0"
                  >
                    {showKey ? 'Hide' : 'Show'}
                  </button>
                </div>
                <p id="access-key-help" className="text-xs text-slate-500 mt-1.5">
                  Paste the key you were given. Keys expire after a short time; ask for a new one if yours no longer works.
                </p>
              </div>

              {error && (
                <p
                  role="alert"
                  className="flex items-start gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2"
                >
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-rose-600" />
                  <span>{error}</span>
                </p>
              )}

              <button
                type="submit"
                disabled={checking}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-sky-600 hover:bg-sky-700 rounded-xl shadow-sm transition-colors disabled:opacity-60 disabled:cursor-wait"
              >
                {checking ? <RefreshCw className="w-4 h-4 animate-spin" /> : <LogIn className="w-4 h-4" />}
                <span>{checking ? 'Signing in...' : 'Sign in'}</span>
              </button>
            </form>

            <div className="mt-6 pt-5 border-t border-slate-100 text-center">
              <button
                type="button"
                onClick={onExploreSample}
                className="text-sm font-medium text-sky-700 hover:text-sky-800 hover:underline"
              >
                Explore with sample data
              </button>
              <p className="text-xs text-slate-400 mt-1">No sign-in needed; nothing is sent to the shop.</p>
            </div>
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
};

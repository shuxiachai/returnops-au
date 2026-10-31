import React, { useState } from 'react';
import { AlertCircle, Info, LogIn, RefreshCw, RotateCcw, UserPlus } from 'lucide-react';
import {
  ApiError,
  NETWORK_ERROR,
  registerCustomerAccount,
  signInWithPassword,
  verifySessionToken,
} from '../api/client';
import { SessionPrincipal } from '../types/domain';
import { SiteFooter } from './SiteFooter';

interface SignInPageProps {
  // Why the page is shown again, for example an ended session.
  notice?: string;
  onSignedIn: (principal: SessionPrincipal, accessKey: string) => void;
  onExploreSample: () => void;
}

type Mode = 'password' | 'register' | 'key';

const UNREACHABLE = 'The service is not reachable right now. Try again in a moment.';
const NO_ACCOUNTS = 'Password sign-in is not available on this server. Use an access key instead.';

function keyError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401 || err.status === 403) {
      return 'This access key was not accepted. It may have expired; ask for a new one.';
    }
    if (err.code === NETWORK_ERROR || err.status >= 500) return UNREACHABLE;
    return err.message;
  }
  return 'Signing in failed. Try again in a moment.';
}

// The server words every refusal of a username or password for the person signing in
// (accounts.py); a server without the routes answers 404 or 405 with no envelope.
function accountError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 404 || err.status === 405) return NO_ACCOUNTS;
    if (err.code === NETWORK_ERROR || err.status >= 500) return UNREACHABLE;
    return err.message;
  }
  return 'Signing in failed. Try again in a moment.';
}

// A masked text field with Show/Hide: the screen may be projected (#111 item 12).
const SecretField: React.FC<{
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  describedBy?: string;
  invalid: boolean;
}> = ({ id, label, value, onChange, autoComplete, describedBy, invalid }) => {
  const [shown, setShown] = useState(false);
  const name = label.toLowerCase();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700 mb-1.5">
        {label}
      </label>
      <div className="flex items-stretch gap-2">
        <input
          id={id}
          type={shown ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={autoComplete}
          spellCheck={false}
          aria-describedby={describedBy}
          aria-invalid={invalid ? true : undefined}
          className="w-full min-w-0 text-sm px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all"
        />
        <button
          type="button"
          onClick={() => setShown((current) => !current)}
          aria-pressed={shown}
          aria-label={shown ? `Hide ${name}` : `Show ${name}`}
          className="px-3 text-xs font-medium text-slate-600 border border-slate-300 rounded-xl hover:bg-slate-100 shrink-0"
        >
          {shown ? 'Hide' : 'Show'}
        </button>
      </div>
    </div>
  );
};

const HEADINGS: Record<Mode, { title: string; intro: string }> = {
  password: {
    title: 'Sign in',
    intro: "Customers see their own returns; the shop's Founder sees the review console. Your account decides which.",
  },
  register: {
    title: 'Create a customer account',
    intro: "For customers of the shop. The Founder's account is set up by the shop and cannot be created here.",
  },
  key: {
    title: 'Sign in with an access key',
    intro: 'For keys issued by the shop, for example on a server without password sign-in.',
  },
};

// The first screen (31 October 2026). Every route checks with the server before anything
// is saved, and the role the server reports for the new session decides the page.
export const SignInPage: React.FC<SignInPageProps> = ({ notice, onSignedIn, onExploreSample }) => {
  const [mode, setMode] = useState<Mode>('password');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [accessKey, setAccessKey] = useState('');
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');

  const switchTo = (next: Mode) => {
    setMode(next);
    setPassword('');
    setConfirmation('');
    setError('');
  };

  const finish = async (token: string) => {
    const principal = await verifySessionToken(token);
    onSignedIn(principal, token);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (checking) return;
    let attempt: () => Promise<void>;
    let describe = accountError;
    if (mode === 'key') {
      const candidate = accessKey.trim();
      if (!candidate) {
        setError('Enter your access key.');
        return;
      }
      attempt = () => finish(candidate);
      describe = keyError;
    } else {
      const name = username.trim();
      if (!name || !password) {
        setError('Enter your username and password.');
        return;
      }
      if (mode === 'register') {
        if (password.length < 8 || password.length > 128) {
          setError('Choose a password of 8 to 128 characters.');
          return;
        }
        if (password !== confirmation) {
          setError('The two passwords do not match.');
          return;
        }
      }
      attempt = async () => {
        const session =
          mode === 'register' ? await registerCustomerAccount(name, password) : await signInWithPassword(name, password);
        await finish(session.access_token);
      };
    }
    setChecking(true);
    setError('');
    try {
      await attempt();
    } catch (err: unknown) {
      setError(describe(err));
      setChecking(false);
    }
  };

  const heading = HEADINGS[mode];
  const submitLabel = mode === 'register' ? 'Create account' : 'Sign in';

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
            <h1 className="text-lg font-semibold text-slate-900">{heading.title}</h1>
            <p className="text-sm text-slate-500 mt-1">{heading.intro}</p>

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
              {mode === 'key' ? (
                <div>
                  <SecretField
                    id="access-key"
                    label="Access key"
                    value={accessKey}
                    onChange={(value) => {
                      setAccessKey(value);
                      setError('');
                    }}
                    autoComplete="off"
                    describedBy="access-key-help"
                    invalid={Boolean(error)}
                  />
                  <p id="access-key-help" className="text-xs text-slate-500 mt-1.5">
                    Paste the key you were given. Keys expire after a short time; ask for a new one if yours no longer works.
                  </p>
                </div>
              ) : (
                <>
                  <div>
                    <label htmlFor="username" className="block text-sm font-medium text-slate-700 mb-1.5">
                      Username
                    </label>
                    <input
                      id="username"
                      type="text"
                      value={username}
                      onChange={(e) => {
                        setUsername(e.target.value);
                        setError('');
                      }}
                      autoComplete="username"
                      autoCapitalize="none"
                      spellCheck={false}
                      maxLength={80}
                      aria-describedby={mode === 'register' ? 'username-help' : undefined}
                      aria-invalid={error ? true : undefined}
                      className="w-full text-sm px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all"
                    />
                    {mode === 'register' && (
                      <p id="username-help" className="text-xs text-slate-500 mt-1.5">
                        3 to 80 letters, digits, - or _, starting with a letter or digit.
                      </p>
                    )}
                  </div>
                  <SecretField
                    id="password"
                    label="Password"
                    value={password}
                    onChange={(value) => {
                      setPassword(value);
                      setError('');
                    }}
                    autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                    describedBy={mode === 'register' ? 'password-help' : undefined}
                    invalid={Boolean(error)}
                  />
                  {mode === 'register' && (
                    <>
                      <p id="password-help" className="text-xs text-slate-500 -mt-2">
                        8 to 128 characters.
                      </p>
                      <SecretField
                        id="password-confirmation"
                        label="Confirm password"
                        value={confirmation}
                        onChange={(value) => {
                          setConfirmation(value);
                          setError('');
                        }}
                        autoComplete="new-password"
                        invalid={Boolean(error)}
                      />
                    </>
                  )}
                </>
              )}

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
                {checking ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : mode === 'register' ? (
                  <UserPlus className="w-4 h-4" />
                ) : (
                  <LogIn className="w-4 h-4" />
                )}
                <span>{checking ? (mode === 'register' ? 'Creating account...' : 'Signing in...') : submitLabel}</span>
              </button>
            </form>

            <div className="mt-4 text-sm text-center text-slate-600">
              {mode === 'password' && (
                <span>
                  New customer?{' '}
                  <button type="button" onClick={() => switchTo('register')} className="font-medium text-sky-700 hover:underline">
                    Create an account
                  </button>
                </span>
              )}
              {mode !== 'password' && (
                <button type="button" onClick={() => switchTo('password')} className="font-medium text-sky-700 hover:underline">
                  {mode === 'register' ? 'Already have an account? Sign in' : 'Sign in with a username and password'}
                </button>
              )}
            </div>

            <div className="mt-6 pt-5 border-t border-slate-100 flex flex-col items-center gap-2 text-center">
              <button
                type="button"
                onClick={onExploreSample}
                className="text-sm font-medium text-sky-700 hover:text-sky-800 hover:underline"
              >
                Explore with sample data
              </button>
              <p className="text-xs text-slate-400 -mt-1">No sign-in needed; nothing is sent to the shop.</p>
              {mode !== 'key' && (
                <button
                  type="button"
                  onClick={() => switchTo('key')}
                  className="text-xs text-slate-500 hover:text-slate-700 hover:underline"
                >
                  Use an access key instead
                </button>
              )}
            </div>
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
};

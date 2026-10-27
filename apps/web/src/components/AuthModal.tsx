import React, { useState, useEffect, useRef } from 'react';
import { X, KeyRound, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import {
  getStoredToken,
  setStoredToken,
  getActiveRole,
  setActiveRole,
  verifySessionToken,
  isMockMode,
  setMockMode,
  ApiError,
} from '../api/client';
import { SessionPrincipal } from '../types/domain';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const [tokenInput, setTokenInput] = useState('');
  // The token field is masked unless the operator asks to see it (#111 item 12).
  const [showToken, setShowToken] = useState(false);
  const [activeRole, setLocalRole] = useState<'CUSTOMER' | 'FOUNDER'>(getActiveRole());
  const [currentSession, setCurrentSession] = useState<SessionPrincipal | null>(null);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [mock, setMock] = useState(isMockMode());
  // Only the latest check may update the status, so an older reply cannot
  // confirm a token that has since been edited.
  const verifyRun = useRef(0);

  useEffect(() => {
    if (isOpen) {
      const stored = getStoredToken();
      const storedMock = isMockMode();
      setTokenInput(stored);
      setShowToken(false);
      setLocalRole(getActiveRole());
      setMock(storedMock);
      verifyToken(stored, storedMock);
    }
  }, [isOpen]);

  const resetVerification = () => {
    verifyRun.current += 1;
    setCurrentSession(null);
    setTestStatus('idle');
    setErrorMessage('');
  };

  // Verify checks the text in the box, not the token saved earlier (#111 item 1).
  // In Live API mode the persona then follows the role the server reports.
  const verifyToken = async (candidate: string, mockSelected: boolean) => {
    const run = ++verifyRun.current;
    setCurrentSession(null);
    setErrorMessage('');
    if (mockSelected) {
      setTestStatus('idle');
      return;
    }
    if (!candidate) {
      setTestStatus('error');
      setErrorMessage('Paste a token first. Nothing was checked.');
      return;
    }
    setTestStatus('testing');
    try {
      const sess = await verifySessionToken(candidate);
      if (run !== verifyRun.current) return;
      setCurrentSession(sess);
      setTestStatus('success');
      if (sess.role === 'CUSTOMER' || sess.role === 'FOUNDER') setLocalRole(sess.role);
    } catch (err: unknown) {
      if (run !== verifyRun.current) return;
      setTestStatus('error');
      setErrorMessage(
        err instanceof ApiError && err.status === 401
          ? 'This token was refused: it has expired or is not valid. Paste a new token from sessions.json.'
          : err instanceof Error
            ? err.message
            : 'Authentication verification failed'
      );
    }
  };

  const handleSave = () => {
    setStoredToken(tokenInput.trim());
    setActiveRole(activeRole);
    setMockMode(mock);
    onClose();
    window.location.reload();
  };

  const handleClear = () => {
    setTokenInput('');
    setStoredToken('');
    resetVerification();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden transform transition-all">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2">
            <KeyRound className="w-5 h-5 text-sky-600" />
            <h3 className="font-semibold text-slate-800 text-base">Authentication & Role Settings</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-200/50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Active Role Selector */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
              Persona & Access Role
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setLocalRole('CUSTOMER')}
                className={`py-2.5 px-3 rounded-xl border text-sm font-medium transition-all text-left flex flex-col ${
                  activeRole === 'CUSTOMER'
                    ? 'border-sky-500 bg-sky-50/70 text-sky-900 shadow-sm'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                <span className="font-semibold">Customer (End-User)</span>
                <span className="text-xs text-slate-500">Lodge and track your own returns</span>
              </button>

              <button
                type="button"
                onClick={() => setLocalRole('FOUNDER')}
                className={`py-2.5 px-3 rounded-xl border text-sm font-medium transition-all text-left flex flex-col ${
                  activeRole === 'FOUNDER'
                    ? 'border-sky-500 bg-sky-50/70 text-sky-900 shadow-sm'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                <span className="font-semibold">Founder (Merchant)</span>
                <span className="text-xs text-slate-500">Review cases, record decisions, view analytics</span>
              </button>
            </div>
          </div>

          {/* Mode Switcher */}
          <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-slate-800">Mock Data Fallback</div>
              <div className="text-xs text-slate-500">
                Use rich built-in synthetic records when local API is offline
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={mock}
                onChange={(e) => {
                  setMock(e.target.checked);
                  resetVerification();
                }}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-600"></div>
            </label>
          </div>

          {/* JWT Input */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label
                htmlFor="auth-token-input"
                className="text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Bearer Token (JWT)
              </label>
              {tokenInput && (
                <button
                  type="button"
                  onClick={handleClear}
                  className="text-xs text-rose-600 hover:underline font-medium"
                >
                  Clear token
                </button>
              )}
            </div>
            {/* Masked by default: the demonstration is shown on a projector, and a
                bearer token is a credential while its session lasts (#111 item 12). */}
            <div className="flex items-stretch gap-2">
              <input
                id="auth-token-input"
                type={showToken ? 'text' : 'password'}
                value={tokenInput}
                onChange={(e) => {
                  setTokenInput(e.target.value);
                  resetVerification();
                }}
                placeholder="Paste JWT issued by returnops_api.demo provision (from sessions.json) or leave blank for mock mode..."
                autoComplete="off"
                spellCheck={false}
                className="w-full text-xs font-mono p-3 bg-slate-50 border border-slate-300 rounded-xl focus:ring-2 focus:ring-sky-500 focus:border-sky-500 focus:bg-white transition-all"
              />
              <button
                type="button"
                onClick={() => setShowToken((shown) => !shown)}
                aria-pressed={showToken}
                aria-label={showToken ? 'Hide token' : 'Show token'}
                className="px-3 text-xs font-medium text-slate-600 border border-slate-300 rounded-xl hover:bg-slate-100 shrink-0"
              >
                {showToken ? 'Hide' : 'Show'}
              </button>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Note: Tokens generated via <code>python -m returnops_api.demo provision</code> are stored in your private <code>sessions.json</code>.
            </p>
          </div>

          {/* Session Verification Status */}
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs">
              {mock && (
                <span className="text-slate-500">Mock Mode uses built-in synthetic data, so no token is checked.</span>
              )}
              {testStatus === 'testing' && (
                <span className="text-slate-500 flex items-center space-x-1">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Validating session...</span>
                </span>
              )}
              {testStatus === 'success' && currentSession && (
                <span className="text-emerald-700 flex items-center space-x-1 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-200">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>
                    Valid: <strong className="font-mono">{currentSession.principal_id}</strong> ({currentSession.role})
                  </span>
                </span>
              )}
              {testStatus === 'error' && (
                <span className="text-rose-700 flex items-center space-x-1 bg-rose-50 px-2 py-1 rounded-md border border-rose-200">
                  <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
                  <span>{errorMessage || 'Unauthenticated / Offline'}</span>
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => verifyToken(tokenInput.trim(), mock)}
              disabled={mock || testStatus === 'testing'}
              className="text-xs text-sky-700 hover:text-sky-800 font-medium hover:underline flex items-center space-x-1 disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Verify</span>
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end space-x-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 font-medium"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="px-5 py-2 text-sm bg-sky-600 hover:bg-sky-700 text-white rounded-xl font-semibold shadow-sm transition-colors"
          >
            Save & Apply
          </button>
        </div>
      </div>
    </div>
  );
};

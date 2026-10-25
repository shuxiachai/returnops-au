import React, { useEffect, useState } from 'react';
import { AlertTriangle, KeyRound } from 'lucide-react';
import { getSessionState, subscribeSessionState, SessionState } from '../api/client';

// The current session state, updated whenever a request reports a 401 or succeeds.
export function useSessionState(): SessionState {
  const [state, setState] = useState<SessionState>(getSessionState());
  useEffect(() => {
    setState(getSessionState());
    return subscribeSessionState(setState);
  }, []);
  return state;
}

interface SessionBannerProps {
  onOpenAuth: () => void;
}

// One on-page banner for an expired or refused token (#111 item 1), instead of a
// browser alert or an error code on each panel.
export const SessionBanner: React.FC<SessionBannerProps> = ({ onOpenAuth }) => {
  const state = useSessionState();
  if (state !== 'rejected') return null;

  return (
    <div role="alert" className="bg-rose-50 border-b border-rose-200 text-rose-900 text-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <span className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>Session expired or not valid. Open Auth Tokens and paste a new token.</span>
        </span>
        <button
          type="button"
          onClick={onOpenAuth}
          className="self-start sm:self-auto px-3 py-1.5 bg-white hover:bg-rose-100 text-rose-800 border border-rose-300 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
        >
          <KeyRound className="w-3.5 h-3.5" />
          <span>Open Auth Tokens</span>
        </button>
      </div>
    </div>
  );
};

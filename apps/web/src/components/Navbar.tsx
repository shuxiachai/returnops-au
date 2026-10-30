import React from 'react';
import {
  RotateCcw,
  ShieldCheck,
  User,
  Database,
  Wifi,
  KeyRound,
} from 'lucide-react';
import {
  getStoredToken,
  isMockMode,
  setMockMode,
  getActiveRole,
  setActiveRole,
  getSession,
} from '../api/client';
import { SessionPrincipal } from '../types/domain';
import { useSessionState } from './SessionBanner';

interface NavbarProps {
  currentTab: 'customer' | 'founder';
  onTabChange: (tab: 'customer' | 'founder') => void;
  onOpenAuth: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentTab,
  onTabChange,
  onOpenAuth,
}) => {
  const [mockActive, setMockActive] = React.useState(isMockMode());
  const token = getStoredToken();
  const role = getActiveRole();
  const sessionState = useSessionState();
  // In Live API mode the badge shows the principal and role the server reports for
  // the saved token, not the persona stored in the browser (#111 item 1).
  const [principal, setPrincipal] = React.useState<SessionPrincipal | null>(null);

  React.useEffect(() => {
    if (mockActive || !token) {
      setPrincipal(null);
      return;
    }
    let cancelled = false;
    getSession()
      .then((session) => {
        if (!cancelled) setPrincipal(session);
      })
      .catch(() => {
        if (!cancelled) setPrincipal(null);
      });
    return () => {
      cancelled = true;
    };
  }, [mockActive, token]);

  let sessionLabel: string | null;
  let sessionDot = 'bg-emerald-500';
  if (mockActive) {
    sessionLabel = token ? role : null;
  } else if (sessionState === 'rejected' || !token) {
    sessionLabel = 'Signed out';
    sessionDot = 'bg-rose-500';
  } else if (principal) {
    sessionLabel = `${principal.role} · ${principal.principal_id}`;
  } else {
    sessionLabel = 'Not verified';
    sessionDot = 'bg-slate-400';
  }

  const handleToggleMock = () => {
    const next = !mockActive;
    setMockActive(next);
    setMockMode(next);
    window.location.reload();
  };

  const handleRoleChange = (newRole: 'CUSTOMER' | 'FOUNDER') => {
    setActiveRole(newRole);
    if (newRole === 'CUSTOMER' && currentTab !== 'customer') {
      onTabChange('customer');
    } else if (newRole === 'FOUNDER' && currentTab !== 'founder') {
      onTabChange('founder');
    }
  };

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Wraps onto more rows on a narrow screen, so no control is pushed off it. */}
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2 min-h-16">
          {/* Brand Logo & Title */}
          <div className="flex items-center space-x-3">
            <div className="bg-sky-600 text-white p-2 rounded-xl shadow-md flex items-center justify-center">
              <RotateCcw className="w-6 h-6 animate-spin-slow" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg text-slate-900 tracking-tight whitespace-nowrap">
                  ReturnOps AU
                </span>
                <span className="bg-sky-50 text-sky-700 border border-sky-200 text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap">
                  ELEC5620 · Group 10
                </span>
              </div>
              <p className="hidden xl:block text-xs text-slate-500 font-medium">
                Returns assistant for a small Australian online shop
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex space-x-1 bg-slate-100 p-1 rounded-xl">
            <button
              onClick={() => {
                handleRoleChange('CUSTOMER');
                onTabChange('customer');
              }}
              className={`flex items-center space-x-2 px-3 xl:px-4 py-2 text-sm font-medium rounded-lg transition-all whitespace-nowrap ${
                currentTab === 'customer'
                  ? 'bg-white text-sky-700 shadow-sm font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
              }`}
            >
              <User className="w-4 h-4" />
              <span>Customer Portal</span>
            </button>

            <button
              onClick={() => {
                handleRoleChange('FOUNDER');
                onTabChange('founder');
              }}
              className={`flex items-center space-x-2 px-3 xl:px-4 py-2 text-sm font-medium rounded-lg transition-all whitespace-nowrap ${
                currentTab === 'founder'
                  ? 'bg-white text-sky-700 shadow-sm font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
              }`}
            >
              <ShieldCheck className="w-4 h-4" />
              <span>Founder Console</span>
            </button>
          </nav>

          {/* Connection Mode & Auth Controls */}
          <div className="flex items-center space-x-3">
            {/* Mock vs Live Toggle */}
            <button
              onClick={handleToggleMock}
              title={mockActive ? 'Switch to Live API Mode' : 'Switch to Mock Data Mode'}
              className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors whitespace-nowrap ${
                mockActive
                  ? 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100'
                  : 'bg-emerald-50 text-emerald-800 border-emerald-300 hover:bg-emerald-100'
              }`}
            >
              {mockActive ? (
                <>
                  <Database className="w-3.5 h-3.5 text-amber-600" />
                  <span>Mock Mode</span>
                </>
              ) : (
                <>
                  <Wifi className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Live API</span>
                </>
              )}
            </button>

            {/* Auth Button */}
            <button
              onClick={onOpenAuth}
              aria-label={sessionLabel ? `Auth Tokens: ${sessionLabel}` : 'Auth Tokens'}
              title={sessionLabel ? `Auth Tokens: ${sessionLabel}` : 'Auth Tokens'}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium border border-slate-300 transition-colors whitespace-nowrap"
            >
              <KeyRound className="w-3.5 h-3.5 text-slate-500" />
              {/* Below 1280 px only the status shows; the button keeps its full accessible name. */}
              <span className={sessionLabel ? 'hidden xl:inline' : ''}>Auth Tokens</span>
              {sessionLabel && (
                <span className="flex items-center space-x-1">
                  <span className={`w-2 h-2 rounded-full ${sessionDot} inline-block`}></span>
                  <span className="font-mono max-w-[7rem] xl:max-w-[11rem] truncate">{sessionLabel}</span>
                </span>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

import React from 'react';
import { RotateCcw, ShieldCheck, User, Database, FlaskConical, LogOut } from 'lucide-react';
import { setActiveRole } from '../api/client';
import { SessionPrincipal } from '../types/domain';

interface NavbarProps {
  // 'live': signed in against the server; 'sample': the built-in sample data.
  mode: 'live' | 'sample';
  // Live mode: who the server says is signed in.
  principal: SessionPrincipal | null;
  currentTab: 'customer' | 'founder';
  onTabChange: (tab: 'customer' | 'founder') => void;
  onSignOut: () => void;
  onExitSample: () => void;
}

const ROLE_LABEL: Record<SessionPrincipal['role'], string> = {
  CUSTOMER: 'Customer',
  FOUNDER: 'Founder',
};

export const Navbar: React.FC<NavbarProps> = ({
  mode,
  principal,
  currentTab,
  onTabChange,
  onSignOut,
  onExitSample,
}) => {
  // Only the sample data has a page switch: signed in, the server's role decides
  // the page, so a switch could only open a page the session may not read.
  const handleSampleTab = (tab: 'customer' | 'founder') => {
    setActiveRole(tab === 'founder' ? 'FOUNDER' : 'CUSTOMER');
    onTabChange(tab);
  };

  const tabClass = (tab: 'customer' | 'founder') =>
    `flex items-center space-x-2 px-3 xl:px-4 py-2 text-sm font-medium rounded-lg transition-all whitespace-nowrap ${
      currentTab === tab
        ? 'bg-white text-sky-700 shadow-sm font-semibold'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
    }`;

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-40 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Wraps onto more rows on a narrow screen, so no control is pushed off it. */}
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2 min-h-16">
          {/* Brand */}
          <div className="flex items-center space-x-3">
            <div className="bg-sky-600 text-white p-2 rounded-xl shadow-md flex items-center justify-center">
              <RotateCcw className="w-6 h-6" />
            </div>
            <div>
              <span className="font-bold text-lg text-slate-900 tracking-tight whitespace-nowrap">ReturnOps AU</span>
              <p className="hidden xl:block text-xs text-slate-500 font-medium">
                Returns assistant for a small Australian online shop
              </p>
            </div>
          </div>

          {mode === 'sample' && (
            <nav aria-label="Sample pages" className="flex space-x-1 bg-slate-100 p-1 rounded-xl">
              <button type="button" onClick={() => handleSampleTab('customer')} className={tabClass('customer')}>
                <User className="w-4 h-4" />
                <span>Customer Portal</span>
              </button>
              <button type="button" onClick={() => handleSampleTab('founder')} className={tabClass('founder')}>
                <ShieldCheck className="w-4 h-4" />
                <span>Founder Console</span>
              </button>
            </nav>
          )}

          {mode === 'sample' ? (
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border bg-amber-50 text-amber-800 border-amber-300 whitespace-nowrap">
                <Database className="w-3.5 h-3.5 text-amber-600" />
                <span>Sample data</span>
              </span>
              <button
                type="button"
                onClick={onExitSample}
                className="px-3 py-1.5 bg-white hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-medium border border-slate-300 transition-colors whitespace-nowrap"
              >
                Exit sample data
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 min-w-0">
              <span
                title="Synthetic records; carriers, payments and messages are simulated."
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border bg-slate-50 text-slate-600 border-slate-300 whitespace-nowrap"
              >
                <FlaskConical className="w-3.5 h-3.5 text-slate-500" />
                <span>Test environment</span>
              </span>
              {principal && (
                <span
                  aria-label={`Signed in as ${principal.principal_id} (${ROLE_LABEL[principal.role]})`}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border border-slate-200 bg-white text-slate-700 min-w-0"
                >
                  {principal.role === 'FOUNDER' ? (
                    <ShieldCheck className="w-3.5 h-3.5 text-sky-600 flex-shrink-0" />
                  ) : (
                    <User className="w-3.5 h-3.5 text-sky-600 flex-shrink-0" />
                  )}
                  <span className="font-semibold">{ROLE_LABEL[principal.role]}</span>
                  <span className="font-mono text-slate-500 truncate max-w-[8rem] xl:max-w-[12rem]">
                    {principal.principal_id}
                  </span>
                </span>
              )}
              <button
                type="button"
                onClick={onSignOut}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-medium border border-slate-300 transition-colors whitespace-nowrap"
              >
                <LogOut className="w-3.5 h-3.5 text-slate-500" />
                <span>Sign out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

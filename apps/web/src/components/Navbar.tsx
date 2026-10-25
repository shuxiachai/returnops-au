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
} from '../api/client';

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
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo & Title */}
          <div className="flex items-center space-x-3">
            <div className="bg-sky-600 text-white p-2 rounded-xl shadow-md flex items-center justify-center">
              <RotateCcw className="w-6 h-6 animate-spin-slow" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg text-slate-900 tracking-tight">
                  ReturnOps AU
                </span>
                <span className="bg-sky-50 text-sky-700 border border-sky-200 text-xs font-semibold px-2 py-0.5 rounded-full">
                  ELEC5620 · Group 10
                </span>
              </div>
              <p className="text-xs text-slate-500 font-medium">
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
              className={`flex items-center space-x-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
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
              className={`flex items-center space-x-2 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
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
              className={`flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
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
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium border border-slate-300 transition-colors"
            >
              <KeyRound className="w-3.5 h-3.5 text-slate-500" />
              <span>
                {token ? (
                  <span className="flex items-center space-x-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                    <span className="font-mono">{role}</span>
                  </span>
                ) : (
                  'Auth Tokens'
                )}
              </span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

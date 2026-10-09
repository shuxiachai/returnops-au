import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { CustomerPortal } from './pages/CustomerPortal';
import { FounderConsole } from './pages/FounderConsole';
import { AuthModal } from './components/AuthModal';
import { getActiveRole } from './api/client';

export const App: React.FC = () => {
  const initialRole = getActiveRole();
  const [currentTab, setCurrentTab] = useState<'customer' | 'founder'>(
    initialRole === 'FOUNDER' ? 'founder' : 'customer'
  );
  const [authModalOpen, setAuthModalOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      {/* Top Navigation */}
      <Navbar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        onOpenAuth={() => setAuthModalOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1 pb-16">
        {currentTab === 'customer' ? <CustomerPortal /> : <FounderConsole />}
      </main>

      {/* Auth Settings Modal */}
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-6 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div>
            <span className="font-semibold text-slate-700">ReturnOps AU</span> · University of Sydney · ELEC5620 Stage 2
          </div>
          <div className="flex items-center space-x-4 text-slate-400">
            <span>Member B: Chengsi Li (Front-end & Portal Lead)</span>
            <span>·</span>
            <span>UC-01 / UC-01E / UC-04 / OF-006</span>
          </div>
        </div>
      </footer>
    </div>
  );
};
export default App;

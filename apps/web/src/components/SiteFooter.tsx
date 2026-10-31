import React from 'react';

// One footer for every screen. The test-environment line stays: everything the
// service handles is synthetic and every provider is simulated (docs/00 Gate 1).
export const SiteFooter: React.FC = () => (
  <footer className="border-t border-slate-200 bg-white py-5 text-xs text-slate-500">
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
      <span className="font-medium text-slate-600">© 2026 ReturnOps AU</span>
      <span className="text-slate-400 text-center sm:text-right">
        Test environment: synthetic records; carriers, payments and messages are simulated. ELEC5620 Group 10, University of Sydney.
      </span>
    </div>
  </footer>
);

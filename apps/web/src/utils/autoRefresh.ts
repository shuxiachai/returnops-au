import { useEffect, useRef } from 'react';
import { getSessionState } from '../api/client';
import { CaseStatus } from '../types/domain';

// Auto-refresh (#111 item 2). A case in one of these statuses will not change
// again, so nothing polls it.
export const FINAL_CASE_STATUSES: readonly CaseStatus[] = ['COMPLETED', 'REJECTED', 'MANUAL_HANDLED'];

export function isFinalStatus(status?: CaseStatus): boolean {
  return status !== undefined && FINAL_CASE_STATUSES.includes(status);
}

export const AUTO_REFRESH_INTERVAL_MS = 5000;

// Focus and visibilitychange usually fire together when the user comes back, so
// a second event within this window is ignored.
const RETURN_DEBOUNCE_MS = 1000;

/** Calls onReturn when the window regains focus or the tab becomes visible again. */
export function useRefreshOnReturn(onReturn: () => void): void {
  const callback = useRef(onReturn);
  callback.current = onReturn;

  useEffect(() => {
    let lastRun = 0;
    const run = () => {
      // An ended session sends nothing more until the user signs in again (runtime review).
      if (getSessionState() === 'rejected') return;
      const now = Date.now();
      if (now - lastRun < RETURN_DEBOUNCE_MS) return;
      lastRun = now;
      callback.current();
    };
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') run();
    };
    window.addEventListener('focus', run);
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      window.removeEventListener('focus', run);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);
}

/**
 * Calls onTick every intervalMs while active. Nothing is sent while the tab is
 * hidden: every customer read takes the exclusive database fence and writes
 * snapshot rows (#106).
 */
export function usePolling(onTick: () => void, active: boolean, intervalMs = AUTO_REFRESH_INTERVAL_MS): void {
  const callback = useRef(onTick);
  callback.current = onTick;

  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === 'hidden' || getSessionState() === 'rejected') return;
      callback.current();
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [active, intervalMs]);
}

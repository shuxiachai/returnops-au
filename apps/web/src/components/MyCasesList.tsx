import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronUp, ListChecks, RefreshCw } from 'lucide-react';
import { ApiError, listMyCases } from '../api/client';
import type { CustomerCaseSummary, CustomerCaseView } from '../types/domain';
import { formatCustomerStatus, formatDate, formatRequestedOutcome, getStatusBadgeClass } from '../utils/formatters';

// "My Requests" on Track & Clarify (31 October 2026): the signed-in customer's own
// cases from GET /v1/cases, outside contract v1. A deployment without password
// sign-in answers 404 or 405 and the list stays hidden; looking a case up by its ID
// works as before. FR-001; NFR-003; UC-01E.
interface MyCasesListProps {
  // The case on screen or being opened; while there is one the list folds away.
  openCaseId: string | null;
  // The open case as last read, so its row follows the page's own refreshes.
  openCase: CustomerCaseView | null;
  onOpen: (caseId: string) => void;
  // The text in the search box above (31 October 2026): rows whose words, status, outcome or
  // case ID contain it stay; the IDs that match go back through onMatches, null while no
  // list is shown, so Enter can open the one match.
  filter?: string;
  onMatches?: (caseIds: string[] | null) => void;
}

function rowMatches(item: CustomerCaseSummary, query: string): boolean {
  const words = [
    item.case_id,
    item.excerpt ?? '',
    formatCustomerStatus(item.status),
    item.awaiting_answer ? 'Your answer is needed' : '',
    item.requested_outcome ? formatRequestedOutcome(item.requested_outcome) : '',
  ];
  return words.some((word) => word.toLowerCase().includes(query));
}

type ListState =
  | { kind: 'loading' }
  | { kind: 'hidden' }
  | { kind: 'failed' }
  | { kind: 'ready'; items: CustomerCaseSummary[]; limit: number };

export const MyCasesList: React.FC<MyCasesListProps> = ({ openCaseId, openCase, onOpen, filter = '', onMatches }) => {
  const [state, setState] = useState<ListState>({ kind: 'loading' });
  // "Show" unfolds the list for the case that is open now; opening another folds it again.
  const [shownWhileOpen, setShownWhileOpen] = useState<string | null>(null);
  const latestLoad = useRef(0);

  const load = async () => {
    const call = ++latestLoad.current;
    setState((current) => (current.kind === 'ready' ? current : { kind: 'loading' }));
    try {
      const list = await listMyCases();
      if (call === latestLoad.current) setState({ kind: 'ready', items: list.items, limit: list.limit });
    } catch (err: unknown) {
      if (call !== latestLoad.current) return;
      setState(err instanceof ApiError && (err.status === 404 || err.status === 405) ? { kind: 'hidden' } : { kind: 'failed' });
    }
  };

  // Read once each time Track & Clarify opens (a case lodged meanwhile is then listed);
  // "Reload list" reads again. A late answer after leaving the tab is dropped.
  useEffect(() => {
    load();
    return () => {
      latestLoad.current += 1;
    };
  }, []);

  const query = filter.trim().toLowerCase();
  const items =
    state.kind === 'ready'
      ? state.items.map((item) =>
          openCase && item.case_id === openCase.case_id
            ? {
                ...item,
                status: openCase.status,
                updated_at: openCase.updated_at,
                awaiting_answer: Boolean(openCase.clarification),
              }
            : item
        )
      : [];
  // Typing a search shows the matches even while a case is open, unless the box holds that
  // case's ID: opening a case puts its ID there, and "Show list" then lists every request.
  const searching = query !== '' && query !== (openCaseId ?? '').toLowerCase();
  const shown = searching ? items.filter((item) => rowMatches(item, query)) : items;
  const shownKey = state.kind === 'ready' ? shown.map((item) => item.case_id).join(' ') : null;
  useEffect(() => {
    onMatches?.(shownKey === null ? null : shownKey ? shownKey.split(' ') : []);
    // shownKey stands for the list of matching IDs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shownKey]);

  if (state.kind === 'hidden') return null;

  const expanded = !openCaseId || shownWhileOpen === openCaseId || searching;

  return (
    <section aria-labelledby="my-requests-heading" className="bg-white rounded-2xl border border-slate-200 shadow-sm">
      <div className="flex items-center justify-between gap-2 px-4 py-3">
        <h2 id="my-requests-heading" className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <ListChecks className="w-4 h-4 text-sky-600" />
          <span>
            My Requests
            {state.kind === 'ready' ? (searching ? ` (${shown.length} of ${items.length})` : ` (${items.length})`) : ''}
          </span>
        </h2>
        <div className="flex items-center gap-1 text-xs text-slate-500">
          <button
            type="button"
            onClick={() => load()}
            aria-label="Reload list"
            title="Reload list"
            className="p-1.5 rounded-lg hover:bg-slate-100 hover:text-sky-600"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          {openCaseId && !searching && (
            <button
              type="button"
              onClick={() => setShownWhileOpen(expanded ? null : openCaseId)}
              aria-expanded={expanded}
              className="px-2 py-1 rounded-lg hover:bg-slate-100 hover:text-sky-600 flex items-center gap-1"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              <span>{expanded ? 'Hide list' : 'Show list'}</span>
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="px-2 pb-2 border-t border-slate-100">
          {state.kind === 'loading' && <p className="px-2 py-3 text-sm text-slate-500">Loading your requests...</p>}
          {state.kind === 'failed' && (
            <p className="px-2 py-3 text-sm text-rose-700">
              Your requests could not be loaded just now. Reload the list, or look a case up by its ID below.
            </p>
          )}
          {state.kind === 'ready' && items.length === 0 && (
            <p className="px-2 py-3 text-sm text-slate-500">
              You have not lodged any requests yet. Use Lodge Return to start one.
            </p>
          )}
          {state.kind === 'ready' && items.length > 0 && shown.length === 0 && (
            <p className="px-2 py-3 text-sm text-slate-500">
              None of your requests matches this. Press Enter to look it up as a case ID.
            </p>
          )}
          {state.kind === 'ready' && shown.length > 0 && (
            <ul className="divide-y divide-slate-100">
              {shown.map((item) => (
                <li key={item.case_id}>
                  <button
                    type="button"
                    onClick={() => onOpen(item.case_id)}
                    aria-current={item.case_id === openCaseId ? 'true' : undefined}
                    className={`w-full text-left px-3 py-3 rounded-xl transition-colors hover:bg-slate-50 ${
                      item.case_id === openCaseId ? 'bg-sky-50' : ''
                    }`}
                  >
                    <div className="text-sm font-medium text-slate-900 break-words">
                      {item.excerpt ?? `Request lodged ${formatDate(item.created_at)}`}
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      {/* A case waiting for the customer says what to do, in place of the status. */}
                      {item.awaiting_answer ? (
                        <span className="px-2 py-0.5 rounded-full font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                          Your answer is needed
                        </span>
                      ) : (
                        <span className={`px-2 py-0.5 rounded-full font-semibold border ${getStatusBadgeClass(item.status)}`}>
                          {formatCustomerStatus(item.status)}
                        </span>
                      )}
                      {item.requested_outcome && item.requested_outcome !== 'UNSPECIFIED' && (
                        <span>Asked for: {formatRequestedOutcome(item.requested_outcome)}</span>
                      )}
                      <span>Lodged {formatDate(item.created_at)}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {state.kind === 'ready' && items.length >= state.limit && (
            <p className="px-3 pt-2 text-xs text-slate-400">
              Showing your {state.limit} most recent requests. Look an older one up by its case ID.
            </p>
          )}
        </div>
      )}
    </section>
  );
};

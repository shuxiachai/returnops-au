import React, { useState } from 'react';
import { Copy, Sparkles } from 'lucide-react';
import { ApiError, draftCustomerReply, summariseRecentCases, triageQueue } from '../api/client';
import type { AiReplyDraft, AiTriage, AiUrgency, AiWeeklySummary } from '../types/domain';
import { formatDate } from '../utils/formatters';

// The Founder AI assistant (31 October 2026): three advisory answers, each asked for by
// the Founder. Nothing is sent to a customer or written to a case; every model-written
// text is rendered as React text, so markup or links in it are never interpreted.
// The routes are outside contract v1 and exist only with password sign-in and the model
// on; a server without them answers 404 or 405 and the panel says so.
// FR-002, FR-012; NFR-002, NFR-003; UC-03, UC-05.

type Ask<T> = { kind: 'idle' } | { kind: 'asking' } | { kind: 'off' } | { kind: 'failed' } | { kind: 'ready'; answer: T };

function useAsk<T>(call: () => Promise<T>) {
  const [state, setState] = useState<Ask<T>>({ kind: 'idle' });
  const ask = async () => {
    setState({ kind: 'asking' });
    try {
      setState({ kind: 'ready', answer: await call() });
    } catch (err: unknown) {
      setState(err instanceof ApiError && (err.status === 404 || err.status === 405) ? { kind: 'off' } : { kind: 'failed' });
    }
  };
  return { state, ask, reset: () => setState({ kind: 'idle' }) };
}

const OFF = 'The AI assistant is not switched on for this deployment.';
const FAILED = 'The AI assistant could not answer just now. Try again in a moment.';

export const URGENCY_LABEL: Record<AiUrgency, string> = { HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low' };
export const URGENCY_CLASS: Record<AiUrgency, string> = {
  HIGH: 'bg-rose-50 text-rose-700 border-rose-200',
  MEDIUM: 'bg-amber-50 text-amber-800 border-amber-200',
  LOW: 'bg-slate-50 text-slate-600 border-slate-200',
};

const AskButton: React.FC<{ label: string; busyLabel: string; busy: boolean; onClick: () => void }> = ({
  label,
  busyLabel,
  busy,
  onClick,
}) => (
  <button
    type="button"
    onClick={onClick}
    disabled={busy}
    className="px-3 py-2 text-xs font-semibold rounded-xl bg-violet-600 hover:bg-violet-700 text-white flex items-center gap-1.5 disabled:opacity-60"
  >
    <Sparkles className={`w-4 h-4 ${busy ? 'animate-pulse' : ''}`} />
    <span>{busy ? busyLabel : label}</span>
  </button>
);

const Note: React.FC<{ answer: { model_id: string; generated_at: string } }> = ({ answer }) => (
  <p className="text-[11px] text-slate-500">
    AI suggestion ({answer.model_id}, {formatDate(answer.generated_at)}). Advisory only: it changes nothing and is sent to
    no one; check it before you rely on it.
  </p>
);

// ---------------------------------------------------------------
// A reply draft for one case, in the customer's language and in English.
// ---------------------------------------------------------------
export const AiReplyDraftPanel: React.FC<{ caseId: string }> = ({ caseId }) => {
  const { state, ask } = useAsk<AiReplyDraft>(() => draftCustomerReply(caseId));
  const [copied, setCopied] = useState(false);
  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <section aria-labelledby="ai-reply-title" className="rounded-2xl p-5 border border-dashed border-violet-300 bg-violet-50/40 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 id="ai-reply-title" className="font-bold text-slate-900 text-sm flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-violet-600" />
          AI reply draft
        </h4>
        {state.kind !== 'off' && (
          <AskButton
            label={state.kind === 'ready' ? 'Draft again' : 'Draft a reply'}
            busyLabel="Drafting..."
            busy={state.kind === 'asking'}
            onClick={() => {
              setCopied(false);
              ask();
            }}
          />
        )}
      </div>
      {state.kind === 'idle' && (
        <p className="text-xs text-slate-600">
          Drafts a short, polite reply in the customer's own language, with an English version for you. It promises no
          outcome; edit it before you use it.
        </p>
      )}
      {state.kind === 'off' && <p className="text-xs text-slate-500">{OFF}</p>}
      {state.kind === 'failed' && <p className="text-xs text-rose-700">{FAILED}</p>}
      {state.kind === 'ready' && (
        <div className="space-y-3">
          {state.answer.customer_language !== 'en' && (
            <div className="space-y-1">
              <div className="text-[11px] font-semibold uppercase text-slate-500">
                In the customer's language ({state.answer.customer_language})
              </div>
              <p className="text-sm text-slate-900 whitespace-pre-wrap break-words bg-white rounded-xl border border-violet-100 p-3">
                {state.answer.reply}
              </p>
            </div>
          )}
          <div className="space-y-1">
            <div className="text-[11px] font-semibold uppercase text-slate-500">English</div>
            <p className="text-sm text-slate-900 whitespace-pre-wrap break-words bg-white rounded-xl border border-violet-100 p-3">
              {state.answer.reply_english}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => copy(state.answer.reply)}
              className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-violet-200 text-violet-800 hover:bg-violet-100 flex items-center gap-1"
            >
              <Copy className="w-3.5 h-3.5" />
              <span>Copy the draft</span>
            </button>
            {copied && <span className="text-[11px] text-emerald-700">Copied.</span>}
          </div>
          <Note answer={state.answer} />
        </div>
      )}
    </section>
  );
};

// ---------------------------------------------------------------
// A triage of the open queue: urgency per case and groups of similar cases.
// ---------------------------------------------------------------
interface AiTriagePanelProps {
  onTriage: (triage: AiTriage | null) => void;
  activeGroup: string | null;
  onGroup: (label: string | null, caseIds: string[] | null) => void;
  onInspect: (caseId: string) => void;
}

export const AiTriagePanel: React.FC<AiTriagePanelProps> = ({ onTriage, activeGroup, onGroup, onInspect }) => {
  const { state, ask } = useAsk<AiTriage>(async () => {
    // The previous marks and group filter go first, so a failed retry leaves none behind.
    onTriage(null);
    const answer = await triageQueue();
    onTriage(answer);
    return answer;
  });
  const urgent = state.kind === 'ready' ? state.answer.cases.filter((c) => c.urgency === 'HIGH') : [];
  return (
    <section aria-labelledby="ai-triage-title" className="rounded-2xl p-4 border border-dashed border-violet-300 bg-violet-50/40 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 id="ai-triage-title" className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-600" />
            AI triage
          </h3>
          <p className="text-xs text-slate-600">
            Marks each open case High, Medium or Low and groups cases about the same problem.
          </p>
        </div>
        {state.kind !== 'off' && (
          <div className="flex items-center gap-2">
            {state.kind === 'ready' && (
              <button
                type="button"
                onClick={() => {
                  onTriage(null);
                  onGroup(null, null);
                }}
                className="px-2 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Clear
              </button>
            )}
            <AskButton
              label={state.kind === 'ready' ? 'Triage again' : 'Triage the queue'}
              busyLabel="Reading the open cases..."
              busy={state.kind === 'asking'}
              onClick={ask}
            />
          </div>
        )}
      </div>
      {state.kind === 'off' && <p className="text-xs text-slate-500">{OFF}</p>}
      {state.kind === 'failed' && <p className="text-xs text-rose-700">{FAILED}</p>}
      {state.kind === 'ready' && (
        <div className="space-y-2">
          {state.answer.considered === 0 ? (
            <p className="text-xs text-slate-600">No open cases to triage.</p>
          ) : urgent.length > 0 ? (
            <div className="text-xs text-slate-800 space-y-1">
              <div className="font-semibold">Read first:</div>
              <ul className="space-y-1">
                {urgent.map((c) => (
                  <li key={c.case_id} className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onInspect(c.case_id)}
                      className="font-mono text-violet-800 underline underline-offset-2 truncate max-w-[14rem]"
                      title={c.case_id}
                    >
                      {c.case_id}
                    </button>
                    <span className="text-slate-600">{c.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-xs text-slate-600">No case was marked High.</p>
          )}
          {state.answer.groups.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-semibold text-slate-700">Similar cases:</span>
              {state.answer.groups.map((g) => (
                <button
                  type="button"
                  key={g.label}
                  aria-pressed={activeGroup === g.label}
                  onClick={() => (activeGroup === g.label ? onGroup(null, null) : onGroup(g.label, g.case_ids))}
                  className={`px-2.5 py-1 rounded-full border font-semibold ${
                    activeGroup === g.label
                      ? 'bg-violet-600 text-white border-violet-600'
                      : 'bg-white text-violet-800 border-violet-200 hover:bg-violet-100'
                  }`}
                >
                  {g.label} ({g.case_ids.length})
                </button>
              ))}
            </div>
          )}
          <Note answer={state.answer} />
        </div>
      )}
    </section>
  );
};

// ---------------------------------------------------------------
// A plain-English summary of the last seven days, from counts only.
// ---------------------------------------------------------------
export const AiWeeklySummaryPanel: React.FC = () => {
  const { state, ask } = useAsk<AiWeeklySummary>(summariseRecentCases);
  return (
    <section aria-labelledby="ai-summary-title" className="rounded-2xl p-5 border border-dashed border-violet-300 bg-violet-50/40 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 id="ai-summary-title" className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-600" />
            AI summary of the last seven days
          </h3>
          <p className="text-xs text-slate-600">Written from the counts below only; no customer's words are sent.</p>
        </div>
        {state.kind !== 'off' && (
          <AskButton
            label={state.kind === 'ready' ? 'Summarise again' : 'Summarise'}
            busyLabel="Summarising..."
            busy={state.kind === 'asking'}
            onClick={ask}
          />
        )}
      </div>
      {state.kind === 'off' && <p className="text-xs text-slate-500">{OFF}</p>}
      {state.kind === 'failed' && <p className="text-xs text-rose-700">{FAILED}</p>}
      {state.kind === 'ready' && (
        <div className="space-y-2">
          <p className="text-sm text-slate-900 whitespace-pre-wrap break-words">{state.answer.summary}</p>
          {state.answer.highlights.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-slate-700 space-y-0.5">
              {state.answer.highlights.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          )}
          {state.answer.model_called ? (
            <Note answer={state.answer} />
          ) : (
            <p className="text-[11px] text-slate-500">No cases in the period, so no model was asked.</p>
          )}
        </div>
      )}
    </section>
  );
};

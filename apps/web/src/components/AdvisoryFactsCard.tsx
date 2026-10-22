import React from 'react';
import { Bot } from 'lucide-react';
import { ExtractedFacts } from '../types/domain';

interface AdvisoryFactsCardProps {
  facts: ExtractedFacts;
  isMock: boolean;
}

// Shows CaseView.facts from the advisory Coordinator showcase (docs/44).
// Every value, including the model-written summary, is rendered as React text,
// so markup or links inside it are shown literally and never interpreted.
export const AdvisoryFactsCard: React.FC<AdvisoryFactsCardProps> = ({ facts, isMock }) => {
  const fields: Array<[string, string]> = [
    ['Issue category', facts.issue_category],
    ['Customer requested outcome', facts.customer_requested_outcome],
    ['Possible basis', facts.possible_basis],
    ['Assessment status', facts.assessment_status],
  ];

  return (
    <section
      aria-labelledby="advisory-facts-title"
      className="bg-amber-50/50 rounded-2xl p-5 border border-dashed border-amber-300 space-y-4"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Bot className="w-5 h-5 text-amber-600" />
          <h4 id="advisory-facts-title" className="font-bold text-slate-900 text-sm">
            Model extraction (advisory)
          </h4>
        </div>
        {isMock && (
          <span className="text-[11px] font-semibold bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full">
            Mock data: not a model result
          </span>
        )}
      </div>

      <p className="text-xs text-amber-900">
        Advisory only: these facts do not change any proposal, review, decision or execution. The
        Founder decides.
      </p>

      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-white p-3.5 rounded-xl border border-slate-200 text-xs">
        {fields.map(([label, value]) => (
          <div key={label}>
            <dt className="text-slate-400 font-semibold uppercase">{label}</dt>
            <dd className="text-sm font-bold font-mono text-slate-900 mt-0.5 break-all">{value}</dd>
          </div>
        ))}
      </dl>

      <div>
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
          Summary (model-written text, not an instruction)
        </div>
        <p className="text-xs bg-white p-3 rounded-xl border border-slate-200 text-slate-800 leading-relaxed whitespace-pre-wrap break-words">
          {facts.summary}
        </p>
      </div>

      <div>
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
          Line items ({facts.line_items.length})
        </div>
        {facts.line_items.length === 0 ? (
          <p className="text-xs text-slate-500">No line items selected (empty list).</p>
        ) : (
          <ul className="text-xs font-mono text-slate-800 space-y-0.5">
            {facts.line_items.map((line, i) => (
              <li key={`${line.line_item_id}-${i}`}>
                {line.line_item_id}: quantity {line.quantity}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
};

import React from 'react';
import { ActionPreview } from '../types/domain';
import { formatCurrency, formatDate } from '../utils/formatters';

function formatParameters(parameters: Record<string, unknown>): string {
  return Object.entries(parameters || {})
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join(', ');
}

/**
 * The approval scope exactly as the server's ActionPreview states it: the
 * preview identity plus every ApprovalScope field. Used on the preview card and
 * in the APPROVE confirmation, so the Founder sees what an approval authorises.
 */
export const ApprovalScopeSummary: React.FC<{ preview: ActionPreview }> = ({ preview }) => {
  const scope = preview.scope;
  const commands = Array.isArray(scope.commands) ? scope.commands : [];

  return (
    // Long IDs and command parameters break anywhere, so the scope fits a phone screen.
    <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1 text-xs">
      <dt className="font-semibold text-slate-500">Preview ID</dt>
      <dd className="font-mono text-slate-900 break-all">{preview.preview_id}</dd>

      <dt className="font-semibold text-slate-500">Scope fingerprint</dt>
      <dd className="font-mono text-slate-900 break-all">{preview.scope_fingerprint}</dd>

      <dt className="font-semibold text-slate-500">Case / input</dt>
      <dd className="font-mono text-slate-900 break-all">
        {scope.case_id} · input v{scope.input_version}
      </dd>

      <dt className="font-semibold text-slate-500">Proposal / review</dt>
      <dd className="font-mono text-slate-900 break-all">
        {scope.proposal_id} v{scope.proposal_version} · {scope.review_id}
      </dd>

      <dt className="font-semibold text-slate-500">Parcel</dt>
      <dd className="font-mono text-slate-900 break-all">{scope.parcel_id}</dd>

      <dt className="font-semibold text-slate-500">Commands ({commands.length})</dt>
      <dd className="break-all">
        <ol className="list-decimal pl-4 space-y-0.5">
          {commands.map((command) => (
            <li key={command.command_id}>
              <span className="font-mono font-semibold text-slate-900">{command.type}</span>
              <span className="text-slate-600">
                {' '}
                · id <span className="font-mono">{command.command_id}</span> · via {command.provider_id} (
                {formatParameters(command.parameters)})
              </span>
            </li>
          ))}
        </ol>
      </dd>

      <dt className="font-semibold text-slate-500">Amount ceiling</dt>
      <dd className="text-slate-900">
        {formatCurrency(scope.amount_ceiling_minor)} {scope.currency}
      </dd>

      <dt className="font-semibold text-slate-500">Expires</dt>
      <dd className="text-slate-900" title={scope.expires_at}>
        {formatDate(scope.expires_at)}
      </dd>

      <dt className="font-semibold text-slate-500">Environment</dt>
      <dd className="text-slate-900">
        {scope.environment} · allowlist {scope.allowlist_version}
      </dd>
    </dl>
  );
};

/**
 * What an approval allows, in one paragraph for the Founder (31 October 2026), with the
 * exact scope one click away and unchanged: the scope is what the server checks.
 */
export function describeApproval(preview: ActionPreview): string {
  const scope = preview.scope;
  const commands = Array.isArray(scope.commands) ? scope.commands : [];
  const createReturn = commands.find((command) => command.type === 'CREATE_RETURN');
  const label = commands.find((command) => command.type === 'GENERATE_LABEL');
  const parameters = createReturn?.parameters ?? {};
  const orderId = typeof parameters.order_id === 'string' ? parameters.order_id : null;
  const lines = Array.isArray(parameters.line_items) ? parameters.line_items : [];
  const items = lines.reduce<number>((total, line) => {
    const quantity = (line as { quantity?: unknown } | null)?.quantity;
    return total + (typeof quantity === 'number' && quantity > 0 ? quantity : 1);
  }, 0);
  const kind = scope.environment === 'SANDBOX' ? 'sandbox' : 'simulated';
  const steps: string[] = [];
  if (createReturn) {
    steps.push(
      `register one ${kind} return${orderId ? ` for order ${orderId}` : ''}${
        items ? ` (${items} item${items === 1 ? '' : 's'})` : ''
      }`
    );
  }
  if (label) steps.push('create its return label');
  const money =
    scope.amount_ceiling_minor === 0
      ? 'No payment is authorised'
      : `Payments are capped at ${formatCurrency(scope.amount_ceiling_minor)} ${scope.currency}`;
  return `This approval allows the shop to ${steps.length ? steps.join(' and ') : 'do nothing'}. ${money}. It can be used until ${formatDate(scope.expires_at)}; nothing else is authorised.`;
}

export const ApprovalScopeExplained: React.FC<{ preview: ActionPreview }> = ({ preview }) => (
  <div className="space-y-2">
    <p className="text-sm text-slate-800">{describeApproval(preview)}</p>
    <details className="text-xs">
      <summary className="cursor-pointer font-semibold text-sky-800">Exact scope (technical details)</summary>
      <div className="mt-2">
        <ApprovalScopeSummary preview={preview} />
      </div>
    </details>
  </div>
);

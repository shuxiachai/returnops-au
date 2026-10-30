import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ApprovalScopeSummary } from './ApprovalScopeSummary';
import type { ActionPreview } from '../types/domain';

// Server IDs are "prefix_" plus 32 hexadecimal characters: on a phone they must
// break inside the scope list instead of widening the Approve confirmation.
const ID = (prefix: string) => `${prefix}_${'9f3a'.repeat(8)}`;

const PREVIEW: ActionPreview = {
  preview_id: ID('preview'),
  scope_fingerprint: 'a'.repeat(64),
  scope: {
    case_id: ID('case'),
    input_version: 2,
    proposal_id: ID('proposal'),
    proposal_version: 1,
    review_id: ID('review'),
    parcel_id: ID('parcel'),
    commands: [
      {
        command_id: ID('command'),
        type: 'CREATE_RETURN',
        provider_id: 'provider_mock_au',
        parameters: { order_id: ID('order'), line_items: [{ line_item_id: ID('line'), quantity: 1 }], parcel_id: ID('parcel') },
      },
    ],
    currency: 'AUD',
    amount_ceiling_minor: 0,
    expires_at: '2026-10-31T00:05:00Z',
    allowlist_version: 'allowlist-demo-v1',
    environment: 'SIMULATED',
  },
};

describe('ApprovalScopeSummary on a narrow screen', () => {
  it('lets every long identifier and the command parameters break anywhere', () => {
    render(<ApprovalScopeSummary preview={PREVIEW} />);

    for (const label of ['Preview ID', 'Scope fingerprint', 'Case / input', 'Proposal / review', 'Parcel', 'Commands (1)']) {
      expect(screen.getByText(label).nextElementSibling, label).toHaveClass('break-all');
    }
  });
});

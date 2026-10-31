import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { FounderConsole } from './FounderConsole';
import { setMockMode } from '../api/client';

// The Founder AI assistant in the console (31 October 2026), with the sample data: the
// triage marks the queue and a group filters it; the reply draft sits on Order & Facts;
// the weekly summary sits on the analytics page. FR-012; NFR-006; UC-03, UC-05.
function queueRows() {
  return screen.getAllByRole('row').slice(1);
}

describe('Founder console with the AI assistant (sample data)', () => {
  beforeEach(() => {
    localStorage.clear();
    setMockMode(true);
  });

  afterEach(() => localStorage.clear());

  it('marks the queue with AI urgency and filters it by a group of similar cases', async () => {
    render(<FounderConsole />);
    await screen.findByText('case_demo_001');
    const all = queueRows().length;
    expect(screen.queryByText(/^AI: /)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Triage the queue' }));
    await screen.findByText('Read first:');
    expect(screen.getAllByText(/^AI: (High|Medium|Low)$/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: 'Sample group (2)' }));
    await waitFor(() => expect(queueRows()).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: 'Sample group (2)' }));
    await waitFor(() => expect(queueRows()).toHaveLength(all));

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
    await waitFor(() => expect(screen.queryByText(/^AI: /)).not.toBeInTheDocument());
  });

  it('offers a reply draft on Order & Facts and a summary on the analytics page', async () => {
    render(<FounderConsole />);
    await screen.findByText('case_demo_001');
    fireEvent.click(within(queueRows()[0]).getByRole('button', { name: /Inspect/ }));
    fireEvent.click(await screen.findByRole('tab', { name: /Order & Facts/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Draft a reply' }));
    expect(await screen.findByText(/Hello, thank you for getting in touch/)).toBeInTheDocument();
    expect(screen.getByText(/Advisory only: it changes nothing and is sent to no one/)).toBeInTheDocument();
  });

  it('summarises the last seven days on the analytics page', async () => {
    render(<FounderConsole />);
    fireEvent.click(screen.getByRole('button', { name: /Analytics Dashboard/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Summarise' }));
    expect(await screen.findByText(/Sample data: \d+ cases in the last seven days/)).toBeInTheDocument();
  });
});

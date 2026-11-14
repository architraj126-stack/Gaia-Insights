import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { StatusChip, type StatusChipState } from './StatusChip';

describe('StatusChip (SPEC 3.2)', () => {
  const states: StatusChipState[] = [
    'Available',
    'Partial',
    'Unavailable',
    'Loading',
    'Failed',
    'Needs validation',
  ];

  states.forEach((status) => {
    it(`renders ${status} state with accessible role and text`, () => {
      render(<StatusChip status={status} />);
      const chip = screen.getByRole('status');
      expect(chip).toBeInTheDocument();
      expect(chip).toHaveTextContent(status);
      expect(chip).toHaveAttribute('aria-label', `Status: ${status}`);
    });
  });

  it('renders custom label when provided', () => {
    render(<StatusChip status="Unavailable" customLabel="Not built yet" />);
    const chip = screen.getByRole('status');
    expect(chip).toHaveTextContent('Not built yet');
    expect(chip).toHaveAttribute('aria-label', 'Status: Not built yet');
  });
});

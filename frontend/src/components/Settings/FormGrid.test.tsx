import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import FormGrid from './FormGrid';

describe('FormGrid', () => {
  it('renders children', () => {
    render(
      <FormGrid>
        <div>Field A</div>
        <div>Field B</div>
      </FormGrid>
    );
    expect(screen.getByText('Field A')).toBeDefined();
    expect(screen.getByText('Field B')).toBeDefined();
  });
});

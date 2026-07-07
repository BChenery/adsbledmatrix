import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Cpu } from 'lucide-react';
import SettingsSection from './SettingsSection';

describe('SettingsSection', () => {
  it('renders title and children', () => {
    render(<SettingsSection title="Test Section">Content</SettingsSection>);
    expect(screen.getByText('Test Section')).toBeDefined();
    expect(screen.getByText('Content')).toBeDefined();
  });

  it('renders icon and description', () => {
    render(
      <SettingsSection title="Test" icon={Cpu} description="A description">
        Content
      </SettingsSection>
    );
    expect(screen.getByText('A description')).toBeDefined();
  });
});

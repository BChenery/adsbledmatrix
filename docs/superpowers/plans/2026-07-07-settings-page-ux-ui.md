# Settings Page UX/UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Settings page so it uses a centred max-width layout, groups controls into clear sections, and is responsive on mobile.

**Architecture:** Introduce small presentational helpers (`SettingsSection`, `FormGrid`) and reorganise the existing `frontend/src/components/Settings/Settings.tsx` JSX into six logical sections. Keep all state, API calls, and validation in `Settings.tsx`.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, shadcn/ui, Vitest, @testing-library/react.

---

## File Structure

| File | Responsibility |
|---|---|
| `frontend/src/components/Settings/SettingsSection.tsx` | Reusable card wrapper with icon, title, and optional description. |
| `frontend/src/components/Settings/FormGrid.tsx` | Responsive two-column grid for paired form fields. |
| `frontend/src/components/Settings/Settings.tsx` | Stateful container: config state, API calls, validation, handlers, and section composition. |
| `frontend/src/components/Settings/Settings.test.tsx` | Integration test verifying sections and save button render. |

---

## Task 1: Create `SettingsSection` helper

**Files:**
- Create: `frontend/src/components/Settings/SettingsSection.tsx`
- Test: `frontend/src/components/Settings/SettingsSection.test.tsx`

- [ ] **Step 1: Write the component**

```tsx
import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

export interface SettingsSectionProps {
  title: string;
  icon?: LucideIcon;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export default function SettingsSection({
  title,
  icon: Icon,
  description,
  children,
  className,
}: SettingsSectionProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle className="text-sm text-white/70 flex items-center gap-2">
          {Icon && <Icon size={14} />}
          {title}
        </CardTitle>
        {description && (
          <p className="text-xs text-white/50 leading-relaxed">{description}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Write the test**

```tsx
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
```

- [ ] **Step 3: Run the test**

Run: `cd frontend && npx vitest run src/components/Settings/SettingsSection.test.tsx`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Settings/SettingsSection.tsx frontend/src/components/Settings/SettingsSection.test.tsx
git commit -m "feat(settings): add SettingsSection helper component"
```

---

## Task 2: Create `FormGrid` helper

**Files:**
- Create: `frontend/src/components/Settings/FormGrid.tsx`
- Test: `frontend/src/components/Settings/FormGrid.test.tsx`

- [ ] **Step 1: Write the component**

```tsx
import React from 'react';
import { cn } from '@/lib/utils';

export interface FormGridProps {
  children: React.ReactNode;
  className?: string;
}

export default function FormGrid({ children, className }: FormGridProps) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 md:grid-cols-2 gap-4',
        className
      )}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 2: Write the test**

```tsx
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
```

- [ ] **Step 3: Run the test**

Run: `cd frontend && npx vitest run src/components/Settings/FormGrid.test.tsx`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Settings/FormGrid.tsx frontend/src/components/Settings/FormGrid.test.tsx
git commit -m "feat(settings): add FormGrid helper component"
```

---

## Task 3: Refactor `Settings.tsx` page shell and Status section

**Files:**
- Modify: `frontend/src/components/Settings/Settings.tsx`

All existing state, hooks, helper functions (`isValidHost`, `isValidPort`, `SelectField`, `LayoutPicker`), and handlers stay unchanged. Only the `return` statement and imports are reorganised.

- [ ] **Step 1: Add imports for the new helpers**

At the top of `frontend/src/components/Settings/Settings.tsx`, add:

```tsx
import SettingsSection from './SettingsSection';
import FormGrid from './FormGrid';
```

- [ ] **Step 2: Replace the page wrapper and loading state**

Find:

```tsx
if (!config) return <div className="p-6 text-white/50">Loading...</div>;

return (
  <div className="p-4 space-y-4">
    <h1 className="text-lg font-semibold">Settings</h1>
```

Replace with:

```tsx
if (!config) return <div className="p-6 text-white/50">Loading...</div>;

return (
  <main className="max-w-3xl mx-auto px-4 py-6 pb-24 space-y-4 md:space-y-6">
    <header className="flex items-center justify-between">
      <h1 className="text-xl font-semibold">Settings</h1>
      {brightnessSaved && (
        <span className="text-xs text-led-accent">Brightness saved</span>
      )}
    </header>
```

- [ ] **Step 3: Wrap the Status card in `SettingsSection`**

Find the first `<Card>` (LED Matrix Status) and replace the opening/closing tags and the `CardHeader` block with `SettingsSection`.

Before:

```tsx
<Card>
  <CardHeader>
    <CardTitle className="text-sm text-white/70 flex items-center gap-2">
      <Cpu size={14} />
      LED Matrix Status
    </CardTitle>
  </CardHeader>
  <CardContent className="space-y-3">
```

After:

```tsx
<SettingsSection title="LED Matrix Status" icon={Cpu}>
```

And close with `</SettingsSection>` instead of `</Card>`.

- [ ] **Step 4: Run lint**

Run: `cd frontend && npm run lint`

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Settings/Settings.tsx
git commit -m "feat(settings): add max-width container and section wrapper to status"
```

---

## Task 4: Refactor Receiver and Location & Units sections

**Files:**
- Modify: `frontend/src/components/Settings/Settings.tsx`

- [ ] **Step 1: Wrap Receiver card in `SettingsSection`**

Find the Receiver `<Card>` and replace its opening/closing with:

```tsx
<SettingsSection title="Receiver" icon={Radio} description="Choose and configure the ADS-B data source.">
```

Close with `</SettingsSection>`.

- [ ] **Step 2: Put host/port fields into `FormGrid`**

Find the host/port inputs inside the `{config.receiver_source === 'network' && (...)}` block and wrap the two field groups in:

```tsx
<FormGrid>
  <div className="space-y-2">{/* Host input */}</div>
  <div className="space-y-2">{/* Port input */}</div>
</FormGrid>
```

- [ ] **Step 3: Wrap Location & Units card in `SettingsSection`**

Find the Location `<Card>` and replace with:

```tsx
<SettingsSection title="Location & Units" icon={Monitor} description="Set your receiver location and preferred units.">
```

Close with `</SettingsSection>`.

- [ ] **Step 4: Put latitude/longitude into `FormGrid`**

Wrap the existing latitude/longitude field group:

```tsx
<FormGrid>
  <div className="space-y-2">{/* Latitude input */}</div>
  <div className="space-y-2">{/* Longitude input */}</div>
</FormGrid>
```

- [ ] **Step 5: Stack unit selects on mobile**

Find the unit selects grid:

```tsx
<div className="grid grid-cols-3 gap-3">
```

Change to:

```tsx
<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
```

- [ ] **Step 6: Run lint and commit**

Run: `cd frontend && npm run lint`

Expected: no errors

```bash
git add frontend/src/components/Settings/Settings.tsx
git commit -m "feat(settings): group receiver and location sections, add responsive grids"
```

---

## Task 5: Refactor Display section (brightness, behaviour, layouts)

**Files:**
- Modify: `frontend/src/components/Settings/Settings.tsx`

- [ ] **Step 1: Wrap Brightness card in `SettingsSection`**

Find the Brightness `<Card>` and replace with:

```tsx
<SettingsSection title="LED Matrix Brightness" icon={Sun} description="Adjust the live matrix brightness. Changes apply immediately.">
```

Close with `</SettingsSection>`.

- [ ] **Step 2: Combine Display Behaviour and Layout cards into one Display section**

Remove the separate "Display Behaviour" card wrapper. Wrap the combined content in:

```tsx
<SettingsSection title="Display" icon={LayoutTemplate} description="Choose what appears on the matrix when aircraft are detected or when idle.">
  {/* display mode selector */}
  {/* cycle interval */}
  {/* aircraft layout picker */}
  {/* idle layout picker */}
</SettingsSection>
```

- [ ] **Step 3: Make LayoutPicker responsive**

Find the `LayoutPicker` component's grid:

```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
```

Change to:

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 gap-3">
```

- [ ] **Step 4: Run lint and commit**

Run: `cd frontend && npm run lint`

Expected: no errors

```bash
git add frontend/src/components/Settings/Settings.tsx
git commit -m "feat(settings): consolidate display section and make layout picker responsive"
```

---

## Task 6: Refactor Night Mode and System sections

**Files:**
- Modify: `frontend/src/components/Settings/Settings.tsx`

- [ ] **Step 1: Wrap Night Mode card in `SettingsSection`**

Find the Night Mode `<Card>` and replace with:

```tsx
<SettingsSection title="Night Mode" icon={Moon} description="Dim or turn off the display during scheduled hours.">
```

Close with `</SettingsSection>`.

- [ ] **Step 2: Put night/sleep time fields into `FormGrid`**

For both the Night Mode and Sleep Mode time field pairs, wrap each pair in:

```tsx
<FormGrid>
  <div className="space-y-2">{/* Start time */}</div>
  <div className="space-y-2">{/* End time */}</div>
</FormGrid>
```

- [ ] **Step 3: Wrap System card in `SettingsSection`**

Find the System Power `<Card>` and replace with:

```tsx
<SettingsSection title="System" icon={Power} description="Update, reboot, or reset the device.">
```

Close with `</SettingsSection>`.

- [ ] **Step 4: Make Save button full-width on mobile**

Find the Save button wrapper:

```tsx
<div className="flex gap-3 pt-4">
  <Button
    onClick={handleSave}
    className="flex-1 gap-2"
    ...
  >
    <Save size={16} />
    Save Settings
  </Button>
</div>
```

Change to:

```tsx
<div className="flex flex-col sm:flex-row gap-3 pt-4">
  <Button
    onClick={handleSave}
    className="w-full sm:flex-1 gap-2"
    ...
  >
    <Save size={16} />
    Save Settings
  </Button>
</div>
```

- [ ] **Step 5: Run lint and commit**

Run: `cd frontend && npm run lint`

Expected: no errors

```bash
git add frontend/src/components/Settings/Settings.tsx
git commit -m "feat(settings): group night mode and system sections, improve save button responsiveness"
```

---

## Task 7: Add `Settings.test.tsx` integration test

**Files:**
- Create: `frontend/src/components/Settings/Settings.test.tsx`

- [ ] **Step 1: Write the test**

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import Settings from './Settings';
import * as apiModule from '@/api/client';
import type { UserConfig } from '@/types/config';

const mockConfig: UserConfig = {
  receiver_source: 'local',
  network_readsb_host: '',
  network_readsb_port: 30005,
  led_matrix_brightness: 50,
  display_mode: 'closest',
  cycle_interval_sec: 5,
  active_layout_id: 1,
  idle_layout_id: 2,
  latitude: -33.8688,
  longitude: 151.2093,
  distance_unit: 'km',
  altitude_unit: 'ft',
  speed_unit: 'kts',
  night_mode: false,
  night_mode_start: '22:00',
  night_mode_end: '06:00',
  sleep_mode: false,
  sleep_mode_start: '23:00',
  sleep_mode_end: '06:00',
  auto_update: false,
  onboarding_complete: true,
  timezone: 'Australia/Sydney',
};

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock('@/hooks/useDisplayStatus', () => ({
  useDisplayStatus: () => null,
}));

vi.mock('@/hooks/useDisplayPreview', () => ({
  useDisplayPreview: () => ({ url: null, error: null }),
}));

vi.mock('@/hooks/useDisplayDiagnostics', () => ({
  useDisplayDiagnostics: () => null,
}));

vi.mock('@/hooks/useLayout', () => ({
  useLayouts: () => ({ layouts: [], loading: false, error: null, refresh: vi.fn() }),
}));

vi.mock('@/hooks/useAircraft', () => ({
  useAircraft: () => [],
}));

vi.mock('@/hooks/useReceiverStatus', () => ({
  useReceiverStatus: () => null,
}));

vi.mock('@/hooks/useUpdateProgress', () => ({
  useUpdateProgress: () => null,
}));

vi.mock('@/components/LocationLookup/LocationLookup', () => ({
  default: () => <div data-testid="location-lookup">LocationLookup</div>,
}));

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiModule.api.get).mockImplementation((url: string) => {
      if (url === '/api/config') {
        return Promise.resolve(mockConfig);
      }
      if (url === '/api/system/update') {
        return Promise.resolve({
          current_version: '1.0.0',
          latest_version: '1.0.0',
          update_available: false,
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
  });

  it('renders settings sections and save button', async () => {
    render(<Settings />);

    expect(await screen.findByRole('heading', { name: /Settings/i })).toBeDefined();
    expect(screen.getByText('LED Matrix Status')).toBeDefined();
    expect(screen.getByText('Receiver')).toBeDefined();
    expect(screen.getByText('LED Matrix Brightness')).toBeDefined();
    expect(screen.getByText('Display')).toBeDefined();
    expect(screen.getByText('Location & Units')).toBeDefined();
    expect(screen.getByText('Night Mode')).toBeDefined();
    expect(screen.getByText('System')).toBeDefined();
    expect(screen.getByRole('button', { name: /Save Settings/i })).toBeDefined();
  });
});
```

- [ ] **Step 2: Run the test**

Run: `cd frontend && npx vitest run src/components/Settings/Settings.test.tsx`

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Settings/Settings.test.tsx
git commit -m "test(settings): add settings page render test"
```

---

## Task 8: Final verification

**Files:**
- Modify: none (read-only verification)

- [ ] **Step 1: Run full test suite**

Run: `cd frontend && npm test`

Expected: all tests pass

- [ ] **Step 2: Run lint**

Run: `cd frontend && npm run lint`

Expected: no errors

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`

Expected: build succeeds

- [ ] **Step 4: Commit if any fixes were needed**

Only commit if lint/tests required changes.

---

## Self-Review

### Spec coverage

- Max-width centred container: Task 3, Step 2.
- Six logical sections: Tasks 3–6.
- Mobile responsiveness: Tasks 3–6 (FormGrid, responsive grids, full-width mobile save button).
- Helper components: Tasks 1–2.
- Unchanged data flow/validation: retained in `Settings.tsx` throughout.
- Tests: Task 7.

### Placeholder scan

No TBD, TODO, or vague instructions. Each step includes exact file paths, code blocks, and commands.

### Type consistency

- `SettingsSectionProps` uses `LucideIcon` imported from `lucide-react`.
- `FormGridProps` uses `React.ReactNode` for children.
- Mocked `UserConfig` matches the existing type shape.

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-07-settings-page-ux-ui.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?

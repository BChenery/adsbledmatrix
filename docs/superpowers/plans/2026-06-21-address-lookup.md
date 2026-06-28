# Address Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a backend-proxied Nominatim address lookup to the Settings page and onboarding wizard, letting users set latitude/longitude by typing an address.

**Architecture:** A new FastAPI endpoint `/api/config/geocode` proxies calls to Nominatim with a proper User-Agent. A reusable React `LocationLookup` component calls this endpoint and notifies its parent of lat/lon changes. The component is dropped into the existing Location card in Settings and the location step of OnboardingWizard.

**Tech Stack:** FastAPI, httpx, SQLAlchemy (existing); React + TypeScript + Tailwind + shadcn/ui (existing); pytest for backend tests.

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/api/config.py` | Add `GET /api/config/geocode` endpoint and `GeocodeResponse` schema. |
| `backend/tests/test_config.py` (new) | Tests for the geocode endpoint with mocked httpx. |
| `frontend/src/components/LocationLookup/LocationLookup.tsx` (new) | Reusable address input + lookup button + result/error display. |
| `frontend/src/components/Settings/Settings.tsx` | Use `LocationLookup` inside the Location card. |
| `frontend/src/components/OnboardingWizard/OnboardingWizard.tsx` | Use `LocationLookup` in the location step. |
| `frontend/src/types/config.ts` | Verify `UserConfig` type is imported/used; no changes expected. |

---

## Task 1: Backend geocode endpoint

**Files:**
- Modify: `backend/app/api/config.py`
- Test: `backend/tests/test_config.py` (create)

- [ ] **Step 1: Add httpx import and response schema**

Open `backend/app/api/config.py`. After the existing imports, add:

```python
import httpx
from fastapi import Query
```

Add the response schema after `ConfigUpdate`:

```python
class GeocodeResponse(BaseModel):
    display_name: str
    latitude: float
    longitude: float
```

- [ ] **Step 2: Add the geocode endpoint**

Append to `backend/app/api/config.py`, after the `update_config` endpoint:

```python
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "ADS-B LED Display / https://github.com/BChenery/adsbledmatrix"


@router.get("/geocode", response_model=GeocodeResponse)
async def geocode_address(q: str = Query(..., min_length=1)):
    """Proxy a geocoding request to Nominatim (OpenStreetMap)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 1},
                headers={"User-Agent": NOMINATIM_USER_AGENT},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Geocoding service returned an error: {e.response.status_code}",
            )
        except httpx.RequestError:
            raise HTTPException(
                status_code=503,
                detail="Geocoding service is unreachable. Please enter coordinates manually.",
            )

    results = response.json()
    if not results:
        raise HTTPException(status_code=404, detail="Address not found.")

    result = results[0]
    try:
        return GeocodeResponse(
            display_name=result["display_name"],
            latitude=float(result["lat"]),
            longitude=float(result["lon"]),
        )
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected response from geocoding service: {e}",
        )
```

- [ ] **Step 3: Write backend tests**

Create `backend/tests/test_config.py`:

```python
import pytest
from httpx import AsyncClient
from fastapi import FastAPI
from app.api.config import router


app = FastAPI()
app.include_router(router)


@pytest.mark.asyncio
async def test_geocode_address_success(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return [
                {
                    "display_name": "Sydney Opera House, Sydney, Australia",
                    "lat": "-33.8568",
                    "lon": "151.2153",
                }
            ]

        def raise_for_status(self):
            pass

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/geocode?q=Sydney%20Opera%20House")

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Sydney Opera House, Sydney, Australia"
    assert data["latitude"] == -33.8568
    assert data["longitude"] == 151.2153


@pytest.mark.asyncio
async def test_geocode_address_not_found(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return []

        def raise_for_status(self):
            pass

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/geocode?q=nowheresville")

    assert response.status_code == 404
    assert "Address not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_geocode_service_error(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, *args, **kwargs):
            from httpx import HTTPStatusError, Response
            raise HTTPStatusError(
                "rate limited",
                request=None,
                response=Response(429, text="rate limited"),
            )

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/geocode?q=Sydney")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_geocode_empty_query():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/geocode?q=")

    assert response.status_code == 422
```

- [ ] **Step 4: Run backend tests to verify they fail**

```bash
cd /home/bchen/Github/adsbledmatrix/backend
.venv/bin/python3 -m pytest tests/test_config.py -v
```

Expected: tests fail because the endpoint/schema is not yet implemented.

- [ ] **Step 5: Implement the endpoint and re-run tests**

Apply the changes from Step 1 and Step 2, then run:

```bash
cd /home/bchen/Github/adsbledmatrix/backend
.venv/bin/python3 -m pytest tests/test_config.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /home/bchen/Github/adsbledmatrix
git add backend/app/api/config.py backend/tests/test_config.py
git commit -m "feat: add Nominatim geocode proxy endpoint"
```

---

## Task 2: Reusable LocationLookup component

**Files:**
- Create: `frontend/src/components/LocationLookup/LocationLookup.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/LocationLookup/LocationLookup.tsx`:

```tsx
import { useState } from 'react';
import { api } from '@/api/client';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Loader2, MapPin } from 'lucide-react';

interface GeocodeResult {
  display_name: string;
  latitude: number;
  longitude: number;
}

interface LocationLookupProps {
  latitude: number;
  longitude: number;
  disabled?: boolean;
  onChange: (lat: number, lon: number) => void;
}

export default function LocationLookup({
  latitude,
  longitude,
  disabled = false,
  onChange,
}: LocationLookupProps) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GeocodeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleLookup = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.get<GeocodeResult>(
        `/api/config/geocode?q=${encodeURIComponent(query.trim())}`
      );
      setResult(res);
      onChange(res.latitude, res.longitude);
    } catch (e: unknown) {
      const message =
        e instanceof Error ? e.message : 'Lookup failed. Please try again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const hasLookupResult =
    result && result.latitude === latitude && result.longitude === longitude;

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label className="flex items-center gap-2">
          <MapPin size={14} />
          Address Lookup
        </Label>
        <div className="flex gap-2">
          <Input
            type="text"
            placeholder="Enter your address or town"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleLookup();
            }}
            disabled={disabled || loading}
            className="flex-1"
          />
          <Button
            onClick={handleLookup}
            disabled={disabled || loading || !query.trim()}
            type="button"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : 'Look up'}
          </Button>
        </div>
        {disabled && (
          <p className="text-xs text-white/40">
            Address lookup is available once the device is connected to the internet.
          </p>
        )}
      </div>

      {error && (
        <div className="text-xs text-red-400 bg-red-950/30 border border-red-900/40 rounded p-2">
          {error}
        </div>
      )}

      {hasLookupResult && (
        <div className="text-xs text-green-400 bg-green-950/30 border border-green-900/40 rounded p-2">
          Found: {result.display_name}
        </div>
      )}

      {!hasLookupResult && !error && result && (
        <div className="text-xs text-amber-400 bg-amber-950/30 border border-amber-900/40 rounded p-2">
          Lookup result differs from current coordinates. Press Look up again or adjust manually.
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify `api.get` supports query strings**

Open `frontend/src/api/client.ts` and confirm `api.get` accepts a URL string. If it wraps axios/fetch and requires a params object, adjust the call to:

```tsx
const res = await api.get<GeocodeResult>('/api/config/geocode', {
  params: { q: query.trim() },
});
```

Read the file first and use whichever pattern matches the existing client.

- [ ] **Step 3: Commit**

```bash
cd /home/bchen/Github/adsbledmatrix
git add frontend/src/components/LocationLookup/LocationLookup.tsx
git commit -m "feat: add reusable LocationLookup component"
```

---

## Task 3: Wire LocationLookup into Settings

**Files:**
- Modify: `frontend/src/components/Settings/Settings.tsx`

- [ ] **Step 1: Import the component**

At the top of `frontend/src/components/Settings/Settings.tsx`, add:

```tsx
import LocationLookup from '@/components/LocationLookup/LocationLookup';
```

- [ ] **Step 2: Insert the lookup above the lat/lon inputs**

In the Location card (`<Card>` starting around line 180), replace the existing `CardContent` block with:

```tsx
        <CardContent className="space-y-4">
          <LocationLookup
            latitude={config.latitude}
            longitude={config.longitude}
            onChange={(lat, lon) => {
              update('latitude', lat);
              update('longitude', lon);
            }}
          />

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Latitude</Label>
              <Input
                type="number"
                step="any"
                value={config.latitude}
                onChange={(e) => update('latitude', parseFloat(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label>Longitude</Label>
              <Input
                type="number"
                step="any"
                value={config.longitude}
                onChange={(e) => update('longitude', parseFloat(e.target.value))}
              />
            </div>
          </div>
        </CardContent>
```

- [ ] **Step 3: Build the frontend**

```bash
cd /home/bchen/Github/adsbledmatrix/frontend
npm run build
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
cd /home/bchen/Github/adsbledmatrix
git add frontend/src/components/Settings/Settings.tsx backend/app/static/
git commit -m "feat: add address lookup to Settings location card"
```

---

## Task 4: Wire LocationLookup into OnboardingWizard

**Files:**
- Modify: `frontend/src/components/OnboardingWizard/OnboardingWizard.tsx`

- [ ] **Step 1: Import the component**

At the top of `frontend/src/components/OnboardingWizard/OnboardingWizard.tsx`, add:

```tsx
import LocationLookup from '@/components/LocationLookup/LocationLookup';
```

- [ ] **Step 2: Add online state and insert lookup**

Inside the component, add an `online` state after the existing state declarations:

```tsx
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
```

Add `useEffect` to the imports from `react`:

```tsx
import { useState, useEffect } from 'react';
```

In the location step (`step === 1`), insert the lookup between the description paragraph and the lat/lon inputs:

```tsx
                <LocationLookup
                  latitude={lat ? parseFloat(lat) : 0}
                  longitude={lon ? parseFloat(lon) : 0}
                  disabled={!online}
                  onChange={(latitude, longitude) => {
                    setLat(latitude.toString());
                    setLon(longitude.toString());
                  }}
                />
```

Use `parseFloat(lat) || 0` if the empty-string case is awkward. The final values are parsed again in `handleFinish`.

- [ ] **Step 3: Build the frontend**

```bash
cd /home/bchen/Github/adsbledmatrix/frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
cd /home/bchen/Github/adsbledmatrix
git add frontend/src/components/OnboardingWizard/OnboardingWizard.tsx backend/app/static/
git commit -m "feat: add address lookup to onboarding location step"
```

---

## Task 5: End-to-end verification

- [ ] **Step 1: Start the backend in dev mode**

```bash
cd /home/bchen/Github/adsbledmatrix/backend
PYTHONPATH=..:. .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: Test the geocode endpoint**

In another terminal:

```bash
curl "http://localhost:8000/api/config/geocode?q=Sydney%20Opera%20House" | python3 -m json.tool
```

Expected: JSON with `display_name`, `latitude`, `longitude`.

- [ ] **Step 3: Start the frontend dev server**

```bash
cd /home/bchen/Github/adsbledmatrix/frontend
npm run dev
```

- [ ] **Step 4: Manual UI test**

Open `http://localhost:5173` (or the dev server URL), navigate to Settings, type an address, click Look up, and verify the lat/lon fields update. Save and refresh to confirm persistence.

- [ ] **Step 5: Run all backend tests**

```bash
cd /home/bchen/Github/adsbledmatrix/backend
.venv/bin/python3 -m pytest tests/test_config.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Production build**

```bash
cd /home/bchen/Github/adsbledmatrix/frontend
npm run build
```

Expected: production build succeeds.

- [ ] **Step 7: Final commit of rebuilt static assets**

If the build produced new hashed asset filenames, commit them:

```bash
cd /home/bchen/Github/adsbledmatrix
git add backend/app/static/
git commit -m "chore: rebuild static assets for address lookup"
```

- [ ] **Step 8: Push**

```bash
cd /home/bchen/Github/adsbledmatrix
git push origin main
```

---

## Self-review checklist

- [ ] Spec coverage: backend proxy endpoint ✓, reusable component ✓, Settings integration ✓, Onboarding integration ✓, error handling ✓, tests ✓.
- [ ] No placeholders: every step has exact code or commands.
- [ ] Type consistency: `GeocodeResponse` matches frontend `GeocodeResult`; `LocationLookupProps.onChange` signature is consistent across usages.
- [ ] httpx is already a project dependency (`backend/pyproject.toml`).
- [ ] The endpoint path `/api/config/geocode` is consistent with the existing `/api/config` router.

# Address Lookup for Location Settings

## Overview

Add an address lookup to the Settings page and the onboarding wizard so users can set their location by typing a street address or place name instead of manually entering latitude/longitude. The lookup uses Nominatim (OpenStreetMap) and is proxied through the backend to avoid CORS issues and to set a proper User-Agent.

## Goals

- Make it easy to correct/update location after the device is on the internet.
- Provide the same lookup UX in both Settings and the onboarding wizard.
- Keep the implementation small, reusable, and privacy-friendly.

## Non-goals

- Live autocomplete/suggestions.
- Reverse geocoding (lat/lon → address).
- Map preview.
- Storing lookup history.

## Design

### Backend

New endpoint:

```
GET /api/config/geocode?q={address}
```

Behavior:

- Receives `q` query parameter (URL-encoded address or place name).
- Calls `https://nominatim.openstreetmap.org/search?q={q}&format=json&limit=1` using `httpx`.
- Sets a descriptive `User-Agent` header (required by Nominatim usage policy): `ADS-B LED Display / https://github.com/BChenery/adsbledmatrix`.
- Returns the first result as JSON:

```json
{
  "display_name": "123 Example Street, Sydney, Australia",
  "latitude": -33.8688,
  "longitude": 151.2093
}
```

- Returns `404` if no results are found.
- Returns `502`/`503` if Nominatim is unreachable or rate-limits the request, with a plain error message.
- Has a short timeout (e.g. 10 seconds) so the UI doesn't hang.

### Frontend

A new reusable component `LocationLookup` is created in `frontend/src/components/LocationLookup/LocationLookup.tsx`.

Props:

```ts
interface LocationLookupProps {
  latitude: number;
  longitude: number;
  disabled?: boolean;
  onChange: (lat: number, lon: number) => void;
}
```

UI:

- Address input field with placeholder, e.g. "Enter your address or town".
- "Look up" button next to the input.
- Loading spinner while the request is in flight.
- On success: show the resolved `display_name` and update the parent lat/lon values.
- On error: show a short inline error message (e.g. "Address not found" or "Lookup service unavailable").

The component is used in:

1. `frontend/src/components/Settings/Settings.tsx` — inside the existing Location card, above the lat/lon inputs. The lat/lon inputs remain visible and editable so users can still fine-tune.
2. `frontend/src/components/OnboardingWizard/OnboardingWizard.tsx` — in the location step, above the lat/lon inputs. If the device has no internet access during onboarding, the lookup is disabled with a note: "Address lookup is available once the device is connected to the internet."

### Error handling

- Empty query: disable the button / do nothing.
- Network error: toast or inline message, lat/lon unchanged.
- No results: inline message "No results found. Try a nearby town or city."
- Rate limit / service error: inline message "Address lookup is temporarily unavailable. Please enter coordinates manually."

### Privacy and rate limits

- No API key is required for Nominatim.
- The backend proxies requests and identifies itself with a project-specific User-Agent.
- Requests are only made when the user explicitly clicks "Look up".

## Testing

- Unit test the backend geocode endpoint with mocked `httpx` responses:
  - successful lookup returns lat/lon/display_name
  - empty results return 404
  - service error returns 502
- Build the frontend and verify the component renders in Settings and Onboarding.
- Manual test: enter a known address and confirm lat/lon update correctly.

## Open questions resolved

- Geocoding service: Nominatim (OpenStreetMap), free, no API key.
- Lookup path: backend proxy (`/api/config/geocode`).
- Scope: Settings page and onboarding wizard.
- Implementation approach: reusable `LocationLookup` component.

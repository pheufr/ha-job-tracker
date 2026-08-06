# Raven House Tools – Frontend/Card Loading Handoff Summary

No code changes were applied in the prior session.  
This file captures the recommended next actions for a new implementation session.

## Likely Root Causes (ranked)

1. **Static path registration logic is unsafe** (`/custom_components/raven_house_tools/frontend.py`)
   - The integration tries both `/local/raven_house_tools` and `/raven_house_tools`.
   - It treats `"already"` exceptions as success, which can create false positives.
   - It then prefers the first “registered” URL (`/local/...`) even if it is not serving integration files.
   - Result: JS URL may resolve to 404 → Lovelace card shows **Configuration Error**.

2. **Auto-injected resources may be unreliable in cast/streamed dashboards**
   - `add_extra_js_url` generally works in standard frontend contexts, but cast/media-tab contexts can be stricter.
   - Many mature cards rely on explicit Lovelace resource loading (`/hacsfiles/...`) instead of runtime injection only.

3. **Frontend JS ships as raw handwritten modern syntax**
   - No transpile/bundle step currently.
   - Cast WebView/browser compatibility can be stricter; syntax mismatches can fail card loading even when URL is reachable.

## Immediate Fixes to Implement (minimal, high-impact)

1. **Harden frontend route registration**
   - In `frontend.py`, register one canonical path only (recommended: `/raven_house_tools`).
   - Do not count exceptions as success unless route availability is confirmed.
   - Only call `add_extra_js_url` after confirmed route registration.

2. **Use canonical URLs for all injected card assets**
   - Inject only `/raven_house_tools/<card>.js?v=<rev>` (avoid `/local/...` preference).

3. **Improve startup diagnostics**
   - Log final injected URLs and route registration result clearly.
   - Log an error for each missing card file under `www/`.

4. **Add README fallback for manual resource setup**
   - Document explicit Lovelace resource registration steps when auto-registration fails.

## Best-Practice Follow-Up (recommended)

1. **Split frontend into a dedicated HACS Lovelace plugin repo**
   - Backend repo: `custom_components/raven_house_tools`
   - Frontend repo: built `dist/*.js` card assets + HACS plugin metadata
   - Resource URL via `/hacsfiles/<repo>/<card>.js`
   - This pattern is generally more robust for cast/streamed dashboard use.

2. **Add frontend build pipeline**
   - Use Rollup/esbuild + transpile target for HA/cast compatibility.
   - Publish built assets in releases.
   - Reduce reliance on integration runtime serving for core card delivery.

## Validation Checklist for Next Session

- Confirm all 5 card JS URLs return HTTP 200 from Home Assistant.
- Verify card behavior on normal dashboard.
- Verify card behavior via media-tab/cast dashboard.
- Test hard refresh + Home Assistant restart behavior.
- Test upgrade path from previous release.

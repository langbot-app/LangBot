# Web UI Testing

## Baseline

- Read shared defaults from `skills/.env`.
- Open `LANGBOT_FRONTEND_URL`.
- Use `LANGBOT_BACKEND_URL` for backend/API/log checks.
- Use Playwright MCP or another browser automation tool with a persisted authenticated profile.

## Workflow

1. Start or verify the backend.
2. Start or verify the selected frontend.
3. Open `LANGBOT_FRONTEND_URL`.
4. Confirm the sidebar shows the logged-in user instead of the login page.
5. Navigate through the target flow with role/text selectors where possible.
6. Check browser console errors, visible UI state, and backend logs.

## Browser Vs API Boundary

Use browser automation as the acceptance path for WebUI cases. API or curl checks are useful for readiness, saved config inspection, and log correlation, but they do not cover login state, form rendering, frontend save behavior, websocket streaming, or console regressions.

For a UI case, curl can support the report but cannot make the case pass by itself. A passing report should include the visible browser result and any backend/API diagnostics that explain the same run.

## Authentication Notes

If the user logged in on one origin but `LANGBOT_FRONTEND_URL` still shows `/login`, copy only the auth state needed for the selected origin. Do not print token values.

## Completion Signal

Report:

- URL tested.
- User action performed.
- Visible result.
- Backend or network confirmation.
- Any console/backend errors that remain.

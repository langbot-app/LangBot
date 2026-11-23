## Cloud plan comparison

`EntitlementSnapshot.plan_revision` and `monthly_bonus_credits` are optional
signed display metadata. The Space adapter opts into these fields with
`plan_metadata=2`. `/api/v1/workspaces/current` exposes them as `current_plan`,
alongside the snapshot's effective limits and feature switches. The existing
Workspace permission check and entitlement resolver remain authoritative.
Admission and quotas do not use plan names or display metadata.

The comparison dialog shows the purchased revision even when the catalog has
no matching plan. It compares resource limits, retention, credits, platform
restrictions and feature switches; identical benefits use one column even if
the revision changed. Missing signed metadata is an explicit unavailable state.
Purchase links for existing paid plans go to Space subscription management,
where permissions, cancellation and revision eligibility are checked again.

This adds display information to an existing authenticated response, not an
agent operation. There is no new MCP operation or billing mutation in Core.
Roll out the matching Core snapshot model before the updated Space adapter.

Verification:

```sh
uv run pytest tests/unit_tests/cloud/test_entitlements.py tests/integration/api/test_workspaces.py -q
cd web
node --test tests/unit/cloud-plans.test.mjs tests/unit/plan-revisions.test.mjs
pnpm build
node tests/revisions/verify.mjs
```

The browser runner expects sibling `space` and `core` checkouts and uses isolated
fixtures and mocked catalog responses. It never authenticates to real Space or
initiates a real payment, and shuts down its own servers after the tests.

Purchased benefits are a card in the existing horizontally scrollable plan card area, immediately before the matching latest plan. There is no separate revision comparison panel, and historical prices are not inferred from the latest catalog.

Customer presentation uses subscription dates and “Latest quotas for this plan”, never revision numbers. Unrelated plans and current latest subscriptions have no comparison markers. Core reuses its normal Benefits card content without diff rows or highlighting. Internal entitlement feature keys are not rendered as product benefits. The optional signed subscription_started_at is the current subscription period start, returned only for a matching entitlement revision; it is not snapshot issuance time. Requests with plan_metadata=1 retain their previous response shape.

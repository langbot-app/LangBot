# Harness direct HTTPS enrollment

This slice adds instance enrollment for the self-hosted edition. It does not
issue account tokens, enroll devices or configure the production chat factory.

Enable it in `data/config.yaml` with `harness.enabled: true`. Set
`harness.instance_origin` to LangBot's HTTPS origin and `harness.client_origin`
to the HTTPS origin hosting Harness. Set `api.tls_certfile` and `api.tls_keyfile`
to the PEM certificate chain and key for the LangBot listener. Certificate
validation must succeed on the client. The backend checks the actual HTTPS
request scheme and does not trust client-supplied forwarding headers.

| Method | `/api/v1/harness` suffix | Contract |
| --- | --- | --- |
| POST | `/registration-links` | Workspace admin or owner; send `{ "label": "My instance", "preferred_auth": "local" }`, with `preferred_auth` optional. Returns `data.id`, `data.url`, `data.fingerprint`, `data.expires_at`. |
| GET | `/registration-links` | List active links issued by the selected Workspace; no token or URL. |
| DELETE | `/registration-links/<id>` | Revoke an unused link from the selected Workspace. |
| POST | `/register` | Direct HTTPS; send `{ "token": "…" }`. Returns `{ "harness_id": "…", "instance_uuid": "…" }` without a response wrapper, matching `registerDirect` in the Harness core. |
| GET | `/bindings` | List active bindings issued by the selected Workspace. |
| DELETE | `/bindings/<id>` | Mark a binding revoked. |

Management uses the existing LangBot WebUI user JWT with `harness.manage` in
the issuing Workspace. That Workspace is management ownership only; redeeming
the URL proves possession of a one-time secret and grants no Workspace access.
Enrollment is instance-scoped. Neither API keys nor support admin sessions can
manage links. These are instance administration and public enrollment routes,
not Application API operations exposed to agents, plugins or MCP.

The link is valid for 30 minutes. Guard it like a password until redeemed. The
database stores a SHA-256 digest, and consumption and binding creation share a
transaction. The initial instance keys persist across restarts; the private
pair is wrapped at rest using the existing instance key wrapping derivation.
The fragment pins public keys for subsequent HTS1 connections. Do not forward
the HTTPS enrollment token through the blind relay. Cloud, secure enrollment
over plain HTTP, live connection revocation and key rotation are follow-ups.

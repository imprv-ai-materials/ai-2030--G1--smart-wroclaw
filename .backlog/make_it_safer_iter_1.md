# Make it safer — iteration 1

Security hardening backlog for `auth_bc` and the app's outbound integrations.
Framed against the "Cross App Access (XAA) / away from static API keys →
short-lived tokens + identity-based access" best practices. Scope kept small on
purpose — this is a first pass, not a rewrite.

## Token lifecycle (`auth_bc`)
- [ ] Shorten access-token TTL to ~15 min (currently 7 days, `config.py:50`) and
      add a rotating **refresh token** (hashed at rest, single-use, reuse-detection).
- [ ] Add `jti` claim + a revocation/denylist so a single leaked token can be
      killed without deleting the account.
- [ ] Add `aud` and `iss` claims and verify them on decode (audience-scoping is
      the core of the token-exchange / XAA model). See `security.py:41-46`.
- [ ] Move JWT signing from static HS256 secret to RS256/JWKS with key rotation
      and `kid` (drop the shared `jwt_secret`, `security.py:19`).

## Secrets & outbound keys (the real "static API keys")
- [ ] Replace long-lived static keys for OpenAI / HERE / Resend with short-lived
      credentials from a secret manager / workload identity (STS / OIDC
      federation) instead of raw `sk-...` in env. See `here_client.py:73`,
      `email/client.py:58`, `bootstrap/__init__.py:79`.
- [ ] Ensure `jwt_secret` / `password_pepper` fail loudly (no boot) when left at
      the insecure dev defaults in a non-local environment (`config.py:49,51`).
- [ ] Add periodic rotation policy + alerting for all above secrets.

## Auth flow hardening
- [ ] Rate-limit / throttle `login`, `register`, `request-password-reset`,
      `resend-confirmation`, `confirm-email` (brute-force + email-bombing).
- [ ] Enforce a password policy (min length / breach check) at `RegisterRequest`.
- [ ] Invalidate all active sessions/refresh tokens on password change & reset
      (`auth_service.py:133-156`).
- [ ] Add basic security headers + explicit CORS allowlist on the API.
- [ ] Add auth audit logging (login success/fail, reset requested/used, role
      changes) without logging tokens or PII.

## Notes
- XAA proper (app↔app / agent↔app delegation via IdP + RFC 8693 token exchange)
  is out of scope for iter 1 — none of it exists yet and it's a bigger design.
  The items above are the prerequisites that make a later XAA story credible.

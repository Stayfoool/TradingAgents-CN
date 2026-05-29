# Staging Deployment

Date: 2026-05-29

This staging profile is for validating custom changes before touching the production compose stack.

## Scope

- Uses a separate Compose project name: `tradingagents-staging`.
- Uses separate container names, MongoDB volume, Redis volume, log directory, and data directory.
- Keeps MongoDB and Redis internal-only when combined with `docker-compose.security.yml`.
- Exposes the web entry point on host port `8080`, leaving production port `80` untouched.

## Start

```bash
docker compose \
  -f docker-compose.hub.nginx.yml \
  -f docker-compose.security.yml \
  -f docker-compose.staging.yml \
  up -d
```

Then validate:

```bash
curl -f http://127.0.0.1:8080/health
curl -f http://127.0.0.1:8080/api/health
```

## Stop

```bash
docker compose \
  -f docker-compose.hub.nginx.yml \
  -f docker-compose.security.yml \
  -f docker-compose.staging.yml \
  down
```

Add `-v` only when you intentionally want to delete staging MongoDB and Redis data.

## Production Promotion Rule

Only promote a change to the production stack after these gates pass:

- `python -m pytest -q tests/quality`
- `yarn type-check`
- `yarn test:unit`
- `yarn vite build`
- `yarn test:e2e`
- staging `/health` and `/api/health` checks

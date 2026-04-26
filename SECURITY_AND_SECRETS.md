# Security and Secrets

## Core rules

- Provider secrets stay backend-only.
- The frontend never stores OpenAI, Tavily, protocols.io, or Consensus credentials.
- OAuth caches and local auth material must never be committed.

## Ignored secret-bearing paths

The repository already ignores:

- `.env`
- `backend/.env`
- `backend/.consensus-home/`
- `.venv`

That includes the Consensus OAuth cache under `.mcp-auth` inside the bridge home.

## Backend-only environment variables

Sensitive values belong in `backend/.env`, for example:

- `OPENAI_API_KEY`
- `TAVILY_API_KEY`
- `PROTOCOLS_IO_TOKEN`
- `SEMANTIC_SCHOLAR_API_KEY`
- Consensus bridge configuration if needed locally

Do not copy these values into:

- frontend code
- Vite env files that are bundled client-side
- screenshots
- checked-in exports

## Consensus OAuth cache

Consensus authentication is local developer state.

Do not commit:

- `backend/.consensus-home/`
- `.mcp-auth/`
- any browser or CLI token cache used to authenticate Consensus MCP

## Export review before commit

Before committing generated exports:

- inspect JSON for accidental headers, tokens, or absolute local paths
- inspect citations for harmless public URLs only
- inspect CSV exports for business-safe content only
- inspect readiness snapshots for status only, not secret values

The current exported artifacts should contain operational content and provider status, not credentials.

## Safe code handoff and zip guidance

For a safe source handoff, prefer tracked files only:

```bash
git archive --format=zip HEAD -o protocolops-source.zip
```

If you want to include generated docs and reviewed exports, make sure they are already tracked and reviewed before archiving.

Do **not** include:

- `backend/.env`
- `.env`
- `backend/.consensus-home/`
- local browser profiles
- unreviewed SQLite DB copies containing secrets or unintended artifacts

## Operational reminders

- keep live-provider tokens local
- rotate tokens if they are ever exposed
- never paste credentials into issue trackers or docs
- never commit OAuth callback artifacts or provider debug logs without inspection


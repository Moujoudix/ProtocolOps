from __future__ import annotations

import httpx

from app.core.config import Settings
from app.models.schemas import ProviderReadiness, ReadinessResponse, ReadinessStatus


class ReadinessService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def build(self) -> ReadinessResponse:
        providers = [
            ProviderReadiness(
                provider="OpenAI",
                status=ReadinessStatus.ready if self.settings.openai_api_key else ReadinessStatus.missing_secret,
                detail="Structured parsing and plan generation",
                configured=bool(self.settings.openai_api_key),
                authenticated=bool(self.settings.openai_api_key),
            ),
            await self._consensus_readiness(),
            ProviderReadiness(
                provider="Tavily",
                status=ReadinessStatus.ready if self.settings.tavily_api_key else ReadinessStatus.missing_secret,
                detail="Supplier discovery and extract",
                configured=bool(self.settings.tavily_api_key),
                authenticated=bool(self.settings.tavily_api_key),
            ),
            ProviderReadiness(
                provider="protocols.io",
                status=ReadinessStatus.ready if self.settings.protocols_io_token else ReadinessStatus.missing_secret,
                detail="Protocol repository access",
                configured=bool(self.settings.protocols_io_token),
                authenticated=bool(self.settings.protocols_io_token),
            ),
            ProviderReadiness(
                provider="Semantic Scholar",
                status=ReadinessStatus.public_mode,
                detail="Public API mode",
                configured=True,
                authenticated=False,
            ),
        ]

        live_ready = all(
            item.status in {ReadinessStatus.ready, ReadinessStatus.public_mode}
            and (item.provider != "Consensus" or item.authenticated)
            for item in providers
        )

        return ReadinessResponse(
            strict_live_mode=self.settings.strict_live_mode,
            live_ready=live_ready,
            providers=providers,
        )

    async def _consensus_readiness(self) -> ProviderReadiness:
        if not self.settings.consensus_mcp_enabled:
            return ProviderReadiness(
                provider="Consensus",
                status=ReadinessStatus.degraded,
                detail="Consensus is disabled",
                configured=False,
                authenticated=False,
            )
        if not self.settings.consensus_mcp_bridge_url:
            return ProviderReadiness(
                provider="Consensus",
                status=ReadinessStatus.missing_secret,
                detail="Consensus bridge URL is not configured",
                configured=False,
                authenticated=False,
            )

        bridge_health = self.settings.consensus_mcp_bridge_url.removesuffix("/search") + "/health"
        try:
            async with httpx.AsyncClient(timeout=min(self.settings.request_timeout_seconds, 5.0)) as client:
                response = await client.get(bridge_health)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            return ProviderReadiness(
                provider="Consensus",
                status=ReadinessStatus.unreachable,
                detail=f"Bridge unreachable: {exc}",
                configured=True,
                authenticated=False,
            )

        authenticated = bool(payload.get("authenticated"))
        return ProviderReadiness(
            provider="Consensus",
            status=ReadinessStatus.ready if authenticated else ReadinessStatus.degraded,
            detail=payload.get("detail") or "Consensus bridge reachable",
            configured=True,
            authenticated=authenticated,
        )

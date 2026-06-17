from __future__ import annotations

import httpx


class ApiFootballClient:
    def __init__(self, base_url: str, api_key: str | None) -> None:
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    async def get_worldcup_fixtures(self, season: int = 2026) -> dict:
        return await self._get('/fixtures', {'league': 1, 'season': season})

    async def get_worldcup_teams(self, season: int = 2026) -> dict:
        return await self._get('/teams', {'league': 1, 'season': season})

    async def get_prediction(self, fixture_id: int) -> dict:
        return await self._get('/predictions', {'fixture': fixture_id})

    async def get_odds(self, fixture_id: int) -> dict:
        return await self._get('/odds', {'fixture': fixture_id})

    async def _get(self, path: str, params: dict) -> dict:
        if not self.api_key:
            raise RuntimeError('API_FOOTBALL_KEY is not configured')
        headers = {'x-apisports-key': self.api_key}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f'{self.base_url}{path}', headers=headers, params=params)
            response.raise_for_status()
            return response.json()

import json
from typing import Dict, List, Optional

import aiohttp

from core.config import config

BASE_URL = "https://api.modrinth.com/v2"
USER_AGENT = "MinecraftBot/1.0 (github.com/MuKeLaNGlo/minecraft-server)"


class ModrinthAPI:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT}
            )
        return self._session

    async def search(
        self, query: str, limit: int = 10, offset: int = 0,
        server_only: bool = False,
        project_type: str = "mod",
        loaders: list[str] | None = None,
    ) -> Dict:
        """Search projects filtered by loader and MC version."""
        loader_facet = [f"categories:{l}" for l in (loaders or [config.mc_loader])]
        facet_list = [
            loader_facet,
            [f"versions:{config.mc_version}"],
            [f"project_type:{project_type}"],
        ]
        if server_only:
            facet_list.append(["server_side:required", "server_side:optional"])
        facets = json.dumps(facet_list)
        params = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "facets": facets,
            "index": "relevance",
        }
        async with self.session.get(f"{BASE_URL}/search", params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_project(self, id_or_slug: str) -> Dict:
        """Get project details by ID or slug."""
        async with self.session.get(f"{BASE_URL}/project/{id_or_slug}") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_versions(
        self,
        project_id: str,
        loaders: list[str] | None = None,
        game_version: Optional[str] = None,
    ) -> List[Dict]:
        """Get project versions filtered by loader(s) and game version."""
        params = {}
        loaders = loaders or [config.mc_loader]
        game_version = game_version or config.mc_version
        if loaders:
            params["loaders"] = json.dumps(loaders)
        if game_version:
            params["game_versions"] = json.dumps([game_version])

        async with self.session.get(
            f"{BASE_URL}/project/{project_id}/version", params=params
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_version(self, version_id: str) -> Dict:
        """Get a specific version by ID."""
        async with self.session.get(f"{BASE_URL}/version/{version_id}") as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_version_by_hash(self, sha512: str) -> Optional[Dict]:
        """Look up a version by file SHA512 hash."""
        try:
            async with self.session.get(
                f"{BASE_URL}/version_file/{sha512}",
                params={"algorithm": "sha512"},
            ) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json()
        except Exception:
            return None

    async def check_updates(
        self, hashes: List[str], loaders: list[str] | None = None,
    ) -> Dict:
        """Check for updates for multiple projects by their SHA512 hashes."""
        payload = {
            "hashes": hashes,
            "algorithm": "sha512",
            "loaders": loaders or [config.mc_loader],
            "game_versions": [config.mc_version],
        }
        async with self.session.post(
            f"{BASE_URL}/version_files/update", json=payload
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


modrinth = ModrinthAPI()

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from core.config import config
from api.auth import authenticate, AuthRequest, AuthResponse
from api.routes.server import router as server_router
from api.routes.players import router as players_router
from api.routes.monitoring import router as monitoring_router
from api.routes.stats import router as stats_router
from api.routes.backups import router as backups_router
from api.routes.worlds import router as worlds_router
from api.routes.mods import router as mods_router
from api.routes.console import router as console_router
from api.routes.scheduler import router as scheduler_router
from api.routes.logs import router as logs_router

# Frontend dist directory — mounted as /web-dist in Docker
_STATIC_DIR = Path("/web-dist")


def create_app() -> FastAPI:
    app = FastAPI(title="MC Bot API", docs_url="/api/docs", openapi_url="/api/openapi.json")

    origins = []
    if config.webapp_domain:
        origins.append(f"https://{config.webapp_domain}")
    origins.append("http://localhost:5173")  # dev

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth endpoint
    @app.post("/api/auth", response_model=AuthResponse)
    async def auth(body: AuthRequest):
        return await authenticate(body)

    # API routes
    app.include_router(server_router)
    app.include_router(players_router)
    app.include_router(monitoring_router)
    app.include_router(stats_router)
    app.include_router(backups_router)
    app.include_router(worlds_router)
    app.include_router(mods_router)
    app.include_router(console_router)
    app.include_router(scheduler_router)
    app.include_router(logs_router)

    # Serve frontend static files
    if _STATIC_DIR.exists():
        # Serve assets with caching
        assets_dir = _STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # SPA fallback — all other routes serve index.html
        @app.get("/{path:path}")
        async def spa_fallback(path: str):
            file_path = _STATIC_DIR / path
            if file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(_STATIC_DIR / "index.html")

    return app

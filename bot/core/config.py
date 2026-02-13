import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _env_str(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int = 0) -> int:
    val = os.getenv(key, "")
    return int(val) if val.isdigit() else default


@dataclass(frozen=True)
class Config:
    # Telegram
    bot_token: str = field(default_factory=lambda: _env_str("BOT_TOKEN"))
    super_admin_id: int = field(default_factory=lambda: _env_int("SUPER_ADMIN_ID"))
    log_chat_id: str = field(default_factory=lambda: _env_str("LOG_CHAT_ID"))

    # RCON
    rcon_host: str = field(default_factory=lambda: _env_str("RCON_HOST", "minecraft"))
    rcon_port: int = field(default_factory=lambda: _env_int("RCON_PORT", 25575))
    rcon_password: str = field(default_factory=lambda: _env_str("RCON_PASSWORD"))

    # Minecraft
    mc_version: str = field(default_factory=lambda: _env_str("MC_VERSION", "1.20.1"))
    mc_type: str = field(default_factory=lambda: _env_str("MC_TYPE", "FORGE"))
    mc_loader: str = field(default_factory=lambda: _env_str("MC_LOADER", "forge"))
    mc_memory: str = field(default_factory=lambda: _env_str("MC_MEMORY", "4G"))
    mc_container_name: str = field(default_factory=lambda: _env_str("MC_CONTAINER_NAME", "mc-server"))

    # LogWatcher
    log_watcher_interval: int = field(default_factory=lambda: _env_int("LOG_WATCHER_INTERVAL", 3))

    # Paths
    mc_data_path: str = "/mc-data"
    backups_path: str = "/backups"
    db_path: str = "/bot-data/bot.db"


config = Config()

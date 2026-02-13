import re

_COLOR_PATTERN = re.compile(r"§[0-9a-fk-or]")
_ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][AB012]|\x1b\[?\d*[a-zA-Z]")

LINE = "━━━━━━━━━━━━━━━━━━━━"


def replace_color_tag(text: str) -> str:
    """Remove Minecraft color/formatting codes from text."""
    return _COLOR_PATTERN.sub("", text)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text (terminal colors, cursor control, etc.)."""
    return _ANSI_PATTERN.sub("", text)


_RCON_NOISE = re.compile(
    r".*\[RCON Client /[\d.]+ #\d+/INFO\]:.*$",
    re.MULTILINE,
)


def clean_log(text: str) -> str:
    """Clean Docker/MC log output: strip ANSI codes, remove RCON noise, trim blank lines."""
    text = strip_ansi(text)
    text = replace_color_tag(text)
    text = _RCON_NOISE.sub("", text)
    # collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate(text: str, max_length: int = 4000) -> str:
    """Truncate text to fit Telegram message limit."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n... (обрезано)"


def format_bytes(size: int) -> str:
    """Human-readable file size."""
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


def format_duration(seconds: int) -> str:
    """Format seconds into human-readable Russian duration."""
    if seconds < 60:
        return f"{seconds} сек"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"


def section_header(emoji: str, title: str, description: str = "") -> str:
    """Format a section header with separator and optional description."""
    parts = [LINE, f"{emoji} <b>{title}</b>", LINE]
    if description:
        parts.append(f"\n{description}")
    return "\n".join(parts)


def progress_bar(value: float, max_value: float, length: int = 10) -> str:
    """Render a text progress bar: ▓▓▓░░░░░░░"""
    if max_value <= 0:
        return "░" * length
    ratio = min(value / max_value, 1.0)
    filled = round(ratio * length)
    return "▓" * filled + "░" * (length - filled)


def status_dot(value: float, warn: float = 70, crit: float = 90) -> str:
    """Return a colored dot based on thresholds."""
    if value >= crit:
        return "🔴"
    if value >= warn:
        return "🟡"
    return "🟢"


def success_text(msg: str) -> str:
    return f"✅ {msg}"


def error_text(msg: str) -> str:
    return f"❌ {msg}"


def warning_text(msg: str) -> str:
    return f"⚠ {msg}"

"""
bot/utils/formatters.py
Utility formatters for human-readable sizes, elapsed time, etc.
"""


def human_size(num_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def elapsed_bar(current: int, total: int, width: int = 20) -> str:
    """Unicode progress bar with time labels."""
    if total <= 0:
        return "▒" * width
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    from bot.music.helpers import format_duration
    return f"{bar} {format_duration(current)} / {format_duration(total)}"


def truncate(text: str, limit: int = 50) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."

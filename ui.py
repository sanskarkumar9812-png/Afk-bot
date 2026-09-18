"""
Shared message-formatting helpers, so every command produces the same
clean, consistent look instead of ad hoc emoji-heavy text.

Style rules used across the bot:
  - One header line per message, bold, short.
  - A thin divider under headers/sections.
  - At most one emoji per line, used as a marker not decoration.
  - Numbers/points right-aligned where it matters via monospace.
"""

DIVIDER = "─" * 24

MEDALS = ["🥇", "🥈", "🥉"]


def header(title: str) -> str:
    return f"*{title}*\n{DIVIDER}"


def rank_line(position: int, name: str, detail: str) -> str:
    marker = MEDALS[position] if position < 3 else f"{position + 1}."
    return f"{marker} {name} — {detail}"


def section(title: str, lines: list) -> str:
    body = "\n".join(lines) if lines else "_Nothing here yet._"
    return f"{header(title)}\n{body}"

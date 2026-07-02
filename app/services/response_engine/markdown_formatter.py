"""Markdown formatting utilities for consistent, polished responses."""

import re
from typing import Any


class MarkdownFormatter:
    """Generates polished markdown from structured response text.

    Handles:
      - Consistent heading styles
      - Bullet list normalization
      - Bold/emphasis patterns
      - Emoji spacing
      - Line spacing
    """

    @staticmethod
    def normalize_heading(text: str) -> str:
        lines = text.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if re.search(r"^[A-Z][A-Za-z\s]+:", stripped) and len(stripped) < 60:
                line = line.replace(stripped, f"**{stripped.rstrip(':')}**", 1)
            result.append(line)
        return "\n".join(result)

    @staticmethod
    def normalize_bullets(text: str) -> str:
        lines = text.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- ") or stripped.startswith("* "):
                indent = line[:len(line) - len(line.lstrip())]
                content = stripped[2:].strip()
                result.append(f"{indent}• {content}")
            else:
                result.append(line)
        return "\n".join(result)

    @staticmethod
    def format_section(heading: str, body: str) -> str:
        parts = [f"**{heading}**", "", body]
        return "\n".join(parts)

    @staticmethod
    def format_list(items: list[str], prefix: str = "•") -> str:
        return "\n".join(f"{prefix} {item}" for item in items)

    @staticmethod
    def format_key_value_pairs(pairs: list[tuple[str, str]]) -> str:
        return "\n".join(f"**{k}:** {v}" for k, v in pairs)

    @staticmethod
    def add_follow_up(suggestion: str) -> str:
        return f"\n\n💡 {suggestion}"

    @staticmethod
    def final_cleanup(text: str) -> str:
        text = MarkdownFormatter.normalize_bullets(text)
        text = re.sub(r" +", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        return text

    @staticmethod
    def render(text: str) -> str:
        """Apply all formatting and return polished markdown."""
        if not text:
            return text
        text = MarkdownFormatter.normalize_heading(text)
        text = MarkdownFormatter.normalize_bullets(text)
        text = MarkdownFormatter.final_cleanup(text)
        return text

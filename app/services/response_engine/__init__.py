"""Backend-First Response Architecture.

Backend decides. Backend formats. AI enhances.

Components:
  ResponseType        — What kind of response we need to generate
  ResponseStrategy    — Whether to use DIRECT, HYBRID, or LLM_ONLY
  TransitIQPersonality — Stylistic personality constants
  ResponseTemplates   — Structured templates for each ResponseType
  MarkdownFormatter   — Polished markdown generation
  ExplanationBuilder  — Backend reasoning in natural language
  ResponseFormatter   — Orchestrator that ties everything together
"""

from app.services.response_engine.response_strategy import (
    ResponseStrategy,
    ResponseDecision,
    decide_strategy,
)
from app.services.response_engine.response_type import ResponseType
from app.services.response_engine.personality import TransitIQPersonality
from app.services.response_engine.response_templates import ResponseTemplates
from app.services.response_engine.markdown_formatter import MarkdownFormatter
from app.services.response_engine.explanation_builder import ExplanationBuilder
from app.services.response_engine.response_formatter import ResponseFormatter

__all__ = [
    "ResponseStrategy",
    "ResponseDecision",
    "decide_strategy",
    "ResponseType",
    "TransitIQPersonality",
    "ResponseTemplates",
    "MarkdownFormatter",
    "ExplanationBuilder",
    "ResponseFormatter",
]

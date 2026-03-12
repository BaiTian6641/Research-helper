"""Prompt injection safety filter for externally-sourced text.

Detects and neutralises prompt injection attempts that may be embedded in
paper abstracts, titles, or user-submitted proposal text before they reach
the LLM.

Threat model
------------
* **Paper abstracts / titles** (arXiv, PubMed, Semantic Scholar, …) — text is
  fetched from third-party APIs and written by authors we do not control.
  Probability of intentional attack is low, but automated pipelines are an
  attractive target for poisoning attacks that try to skew analysis output.

* **User-submitted proposal text** — direct user input that may contain text
  pasted from untrusted sources (e.g. a proposal sent for review that has been
  tampered with).

Attack vectors addressed
------------------------
1. Special model tokens / delimiter injection (``</s>``, ``<|im_end|>``, …)
2. Role override / persona injection ("ignore previous instructions", …)
3. Conversation-marker injection ("Human:", "Assistant:" mid-text)
4. Output format manipulation ("return plain text instead of JSON")
5. System-prompt exfiltration attempts
6. Jailbreak keywords / developer-mode triggers
7. f-string template injection (stray ``{variable}`` references)
8. Homoglyph / invisible Unicode (used to hide injections from visual review)

Design principles
-----------------
* **Never raises** — always returns sanitised text so the pipeline continues
  with degraded but safe data rather than crashing.
* **Logs every detection** at WARNING level with the pattern category so
  operators can audit without exposing raw injected content.
* **Tiered strictness** — abstracts use medium strictness (avoids scientific
  false-positives); proposal text uses high strictness.
* **Redact, not drop** — matched spans are replaced with ``[REDACTED]`` so
  the surrounding context is preserved for analysis.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier 1 — Very high confidence: almost never appear in legitimate academic text
# ---------------------------------------------------------------------------

# Special model tokens / EOS / BOS delimiters.
# Any of these inside a paper abstract means the text is adversarially crafted.
_T1_SPECIAL_TOKENS = re.compile(
    r"""
    </s>                    |   # Llama EOS token
    <\|im_end\|>            |   # Qwen/ChatML end marker
    <\|im_start\|>          |   # Qwen/ChatML start marker
    <\|endoftext\|>         |   # GPT-2 / many HF models
    <\|eot_id\|>            |   # Llama-3 end-of-turn
    <\|assistant\|>         |   # Phi-style role tag
    <\|user\|>              |   # Phi-style role tag
    <\|system\|>            |   # Phi-style role tag
    \[INST\]                |   # Llama-2 / Mistral instruction start
    \[/INST\]               |   # Llama-2 / Mistral instruction end
    <<SYS>>                 |   # Llama-2 system block start
    <</SYS>>                    # Llama-2 system block end
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Direct instruction override — explicit imperative targeting LLM behaviour.
# Phrases like these have essentially zero legitimate use in a research paper.
_T1_INSTRUCTION_OVERRIDE = re.compile(
    r"""
    \b
    (?:
        ignore\s+(?:all\s+)?(?:previous|above|prior|these|any|the\s+above)\s+
            (?:instructions?|rules?|constraints?|prompts?|guidelines?|directives?)
        |
        disregard\s+(?:all\s+)?(?:previous|prior|any|your|the\s+above)\s+
            (?:instructions?|rules?|constraints?|prompts?|directives?)
        |
        forget\s+(?:your|all|every|previous|prior)\s+
            (?:instructions?|rules?|training|directives?|knowledge|constraints?)
        |
        override\s+(?:your|all|previous|the)\s+
            (?:instructions?|rules?|constraints?|prompts?|settings?)
        |
        your\s+new\s+(?:role|persona|identity|instructions?|directives?|task\s+is)
        |
        new\s+(?:system\s+)?(?:prompt|instructions?|directives?|rules?)\s*:
        |
        updated?\s+(?:instructions?|directives?|rules?|prompt)\s*:
        |
        from\s+now\s+on\s+(?:you\s+(?:are|will|must|should)|always|never)
        |
        (?:you\s+must\s+now|you\s+will\s+now|you\s+should\s+now)\s+
            (?:ignore|forget|disregard|override|stop)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Conversation-role markers injected mid-text to simulate a new turn.
# Matches "Human:", "Assistant:", "System:", "AI:", "User:" at start of a line
# or following ≥2 whitespace/newline chars — characteristic of multi-turn poisoning.
_T1_ROLE_MARKERS = re.compile(
    r"""
    (?:^|(?<=\n\n)|(?<=\r\n\r\n))   # start-of-string or after blank line
    \s*
    (?:Human|Assistant|System|AI|User|Bot)
    \s*:\s*
    """,
    re.VERBOSE | re.IGNORECASE | re.MULTILINE,
)

# System-prompt exfiltration patterns.
_T1_EXFILTRATION = re.compile(
    r"""
    \b
    (?:
        (?:print|repeat|reveal|show|tell\s+me|output|display|recite|share|expose|leak)
        \s+(?:your|the|this|my)\s+
        (?:system|initial|original|base|hidden|secret|full|entire|real)\s+
        (?:prompt|instructions?|message|context|configuration|setup)
        |
        what\s+(?:are|were|is)\s+you(?:r)?\s+
        (?:told|instructed|given|real\s+instructions?|base\s+prompt|original\s+instructions?)
        |
        (?:exfiltrate|extract|steal|copy)\s+(?:your|the)\s+
        (?:prompt|instructions?|context|system\s+message)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Jailbreak mode triggers.
_T1_JAILBREAK = re.compile(
    r"""
    \b
    (?:
        (?:enable|activate|enter|turn\s+on)\s+
            (?:developer|jailbreak|dan|unrestricted|god|admin)\s+mode
        |
        \bDANmode\b | \bJAILBREAK\b | \bJAILBROKEN\b
        |
        (?:you\s+have\s+no\s+(?:restrictions?|limitations?|filters?))
        |
        (?:you\s+can\s+(?:do|say|write|output)\s+anything\s+(?:now|without))
        |
        bypass\s+(?:all\s+)?(?:safety|filter|restriction|content|policy|alignment)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Tier 2 — Medium confidence: suspicious in research text, rare false-positives
# ---------------------------------------------------------------------------

# Persona / roleplay injection.
# "act as" is deliberately excluded here — it appears in chemistry ("acts as a catalyst").
# We target unambiguous persona framing: "pretend you are", "roleplay as".
# Allow 0-3 adjective words between the article and the role noun to catch
# "pretend you are an uncensored AI", "pretend you are a free and helpful bot", etc.
_T2_PERSONA_INJECTION = re.compile(
    r"""
    \b
    (?:
        pretend\s+(?:you\s+are|you're|to\s+be)\s+
            (?:[a-z]+\s+){0,3}
            (?:ai\b|llm\b|chatbot|assistant|language\s+model|bot\b|
               uncensored|unfiltered|unaligned|unrestricted|jailbroken|free\s+ai)
        |
        roleplay\s+as\s+(?:a|an|the\s+)?
        |
        you\s+are\s+now\s+(?:[a-z]+\s+){0,2}
            (?:different|unrestricted|new|jailbroken|free|uncensored|unfiltered|unaligned)
        |
        imagine\s+you\s+(?:are|have\s+no)\s+
            (?:restrictions?|limitations?|filters?|alignment|guidelines?)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Output format subversion — trying to make the model return something other than JSON.
_T2_OUTPUT_SUBVERSION = re.compile(
    r"""
    \b
    (?:
        (?:instead\s+of|rather\s+than)\s+(?:returning\s+)?json
        |
        do\s+not\s+(?:return|output|respond\s+with|use)\s+json
        |
        ignore\s+the\s+(?:json\s+)?(?:format|schema|output\s+format)
        |
        (?:respond|reply|answer|write|output)\s+in\s+plain\s+text\s+(?:only\s+)?instead
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Tier 3 — Heuristic / strict-mode only (higher false-positive risk)
# ---------------------------------------------------------------------------

# f-string template injection: bare {variable_name} patterns that could be
# interpreted as Python format-string slots and cause KeyError / substitution.
# Only applied in strict mode because LaTeX uses {x} frequently.
_T3_TEMPLATE_INJECTION = re.compile(
    r"""
    (?<![\\$])          # not preceded by \ or $ (LaTeX)
    \{
    [a-zA-Z_][a-zA-Z0-9_.:\[\]'"]{1,80}
    \}
    (?!\s*[=%])         # not followed by = or % (LaTeX arg / format spec)
    """,
    re.VERBOSE,
)

# ---------------------------------------------------------------------------
# Invisible / homoglyph Unicode
# ---------------------------------------------------------------------------

# Characters used to hide injections from visual inspection while still being
# processed by the tokeniser.
_INVISIBLE_UNICODE = re.compile(
    r"["
    r"\u00ad"           # soft hyphen
    r"\u200b-\u200f"    # zero-width space / joiners / marks
    r"\u202a-\u202e"    # bidi embedding / override chars
    r"\u2060-\u2064"    # word joiner, invisible plus/times/separator
    r"\u206a-\u206f"    # deprecated formatting chars
    r"\ufeff"           # BOM / zero-width no-break space
    r"\ufff9-\ufffb"    # interlinear annotation
    r"\U000e0000-\U000e007f"  # Unicode tag block (used in some attacks)
    r"]",
    re.UNICODE,
)

# Right-to-left override (RTLO, U+202E) and Arabic letter mark — can reverse
# displayed text direction to disguise injections.
_BIDI_OVERRIDE = re.compile(r"[\u202e\u061c\u200f\u200e]")

# ---------------------------------------------------------------------------
# Aggregated pattern lists by tier
# ---------------------------------------------------------------------------

_TIER1_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("special_token_injection", _T1_SPECIAL_TOKENS),
    ("instruction_override", _T1_INSTRUCTION_OVERRIDE),
    ("role_marker_injection", _T1_ROLE_MARKERS),
    ("exfiltration_attempt", _T1_EXFILTRATION),
    ("jailbreak_trigger", _T1_JAILBREAK),
]

_TIER2_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("persona_injection", _T2_PERSONA_INJECTION),
    ("output_format_subversion", _T2_OUTPUT_SUBVERSION),
]

_TIER3_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("template_injection", _T3_TEMPLATE_INJECTION),
]

_REDACTION_MARKER = "[REDACTED]"

# Maximum safe lengths per context (characters, post-sanitisation)
_MAX_LEN: dict[str, int] = {
    "abstract": 1800,   # ~300 words — generous for a real abstract
    "title":    300,    # ~50 words — generous for a real title
    "proposal": 8000,   # user text; safety threshold
    "query":    300,    # search queries are always short
    "generic":  2000,
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SanitisationResult:
    """Outcome of a sanitisation pass."""
    text: str
    was_modified: bool
    detections: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.was_modified


# ---------------------------------------------------------------------------
# Main filter class
# ---------------------------------------------------------------------------

class PromptSafetyFilter:
    """Multi-layer NLP safety filter for prompt-injection prevention.

    Sanitises externally-sourced text before it is interpolated into LLM
    prompt templates.  All detections are logged; the filter never raises.

    Args:
        strict: When True, enable Tier 3 heuristic patterns (template
                injection etc.).  Proposal text always uses strict mode
                regardless of this flag.
    """

    def __init__(self, strict: bool = False):
        self.strict = strict

    # ------------------------------------------------------------------
    # Public convenience methods
    # ------------------------------------------------------------------

    def sanitise_abstract(self, text: str) -> SanitisationResult:
        """Sanitise a single paper abstract (medium-trust, external source)."""
        return self._run(text, context="abstract", extra_strict=False)

    def sanitise_title(self, text: str) -> SanitisationResult:
        """Sanitise a paper title (medium-trust, external source)."""
        return self._run(text, context="title", extra_strict=False)

    def sanitise_proposal(self, text: str) -> SanitisationResult:
        """Sanitise user-supplied proposal text (lower-trust, always strict)."""
        return self._run(text, context="proposal", extra_strict=True)

    def sanitise_query(self, text: str) -> SanitisationResult:
        """Sanitise a user search query (short, bounded)."""
        return self._run(text, context="query", extra_strict=False)

    def sanitise_generic(self, text: str, context: str = "generic") -> SanitisationResult:
        """Sanitise arbitrary externally-sourced text."""
        return self._run(text, context=context, extra_strict=self.strict)

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    def _run(
        self,
        text: str,
        context: str,
        extra_strict: bool,
    ) -> SanitisationResult:
        if not isinstance(text, str) or not text:
            return SanitisationResult(text=text or "", was_modified=False)

        original = text
        detections: list[str] = []

        # Step 1 — Unicode normalisation and invisible char removal
        text = self._clean_unicode(text, context, detections)

        # Step 2 — Remove ASCII control characters (keep \t \n \r)
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
        if cleaned != text:
            detections.append("control_chars")
        text = cleaned

        # Step 3 — Tier 1 patterns (always applied)
        text = self._apply_patterns(_TIER1_PATTERNS, text, context, detections, redact=True)

        # Step 4 — Tier 2 patterns (always applied)
        text = self._apply_patterns(_TIER2_PATTERNS, text, context, detections, redact=True)

        # Step 5 — Tier 3 heuristic patterns (strict / proposal mode only)
        if extra_strict or self.strict:
            text = self._apply_patterns(_TIER3_PATTERNS, text, context, detections, redact=True)

        # Step 6 — Length truncation
        max_len = _MAX_LEN.get(context, _MAX_LEN["generic"])
        if len(text) > max_len:
            text = text[:max_len].rstrip() + "…"
            detections.append("truncated")

        was_modified = text != original
        return SanitisationResult(text=text, was_modified=was_modified, detections=detections)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_unicode(text: str, context: str, detections: list[str]) -> str:
        """NFC-normalise and strip invisible / bidi-override Unicode."""
        text = unicodedata.normalize("NFC", text)

        if _BIDI_OVERRIDE.search(text):
            logger.warning(
                "Bidi-override character detected in %s — likely visual spoofing attempt",
                context,
            )
            detections.append("bidi_override")
            text = _BIDI_OVERRIDE.sub("", text)

        cleaned = _INVISIBLE_UNICODE.sub("", text)
        if cleaned != text:
            detections.append("invisible_unicode")
        return cleaned

    @staticmethod
    def _apply_patterns(
        patterns: list[tuple[str, re.Pattern]],
        text: str,
        context: str,
        detections: list[str],
        redact: bool,
    ) -> str:
        for name, pattern in patterns:
            def _replace(m: re.Match, _n: str = name) -> str:
                snippet = m.group(0)[:80].replace("\n", " ")
                logger.warning(
                    "Prompt injection [%s] detected in %s: '%.80s'",
                    _n, context, snippet,
                )
                detections.append(_n)
                return _REDACTION_MARKER if redact else ""
            text = pattern.sub(_replace, text)
        return text


# ---------------------------------------------------------------------------
# Module-level default instance — import and call directly
# ---------------------------------------------------------------------------

_default_filter = PromptSafetyFilter(strict=False)


def sanitise_abstract(text: str) -> str:
    """Return a sanitised copy of a paper abstract, safe for prompt insertion."""
    return _default_filter.sanitise_abstract(text).text


def sanitise_title(text: str) -> str:
    """Return a sanitised copy of a paper title, safe for prompt insertion."""
    return _default_filter.sanitise_title(text).text


def sanitise_proposal(text: str) -> str:
    """Return a sanitised copy of user-submitted proposal text."""
    return _default_filter.sanitise_proposal(text).text


def sanitise_query(text: str) -> str:
    """Return a sanitised copy of a search query string."""
    return _default_filter.sanitise_query(text).text

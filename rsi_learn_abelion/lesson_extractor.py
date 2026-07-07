"""Extract RSI lessons from tool call events.

Rule-based extraction using heuristic patterns.
Falls back to LLM-only if no pattern matches (tiered architecture).
"""

from __future__ import annotations

import json as _json
import re
import logging
from typing import Optional

from .compressor import Lesson

logger = logging.getLogger(__name__)

# ── 16 heuristic patterns ─────────────────────────────────────────────

_HEURISTICS: list[tuple[re.Pattern, str, str, float]] = [
    (re.compile(r"RecursionError|maximum recursion"),
     "function recurses too deep",
     "add iterative fallback or sys.setrecursionlimit()",
     0.75),
    (re.compile(r"race|thread.*lock|thread.*safe|concurrent.*access"),
     "shared state accessed by multiple threads without lock",
     "protect every read/write with threading.Lock using 'with lock:'",
     0.80),
    (re.compile(r"UnicodeDecode|UnicodeEncode|latin.1|wrong.*encod"),
     "encoding/decoding mismatches",
     "always decode with the same codec that was used to encode; prefer UTF-8",
     0.75),
    (re.compile(r"SQL.*inject|parameter.*query|f.string.*SQL|unrecognized.*token"),
     "building SQL queries with string formatting",
     "use parameterized queries: cursor.execute('WHERE x = ?', (val,))",
     0.85),
    (re.compile(r"Permission denied|EACCES|cannot open file"),
     "file permissions issue",
     "verify the file exists and is readable before opening: os.access() or test -f",
     0.65),
    (re.compile(r"FileNotFound|No such file|does not exist|cannot find"),
     "attempting to operate on a missing file",
     "confirm path exists first: os.path.exists() or ls/find",
     0.70),
    (re.compile(r"TypeError.*NoneType|not subscriptable|NoneType.*attribute"),
     "accessing attribute/method on a None value",
     "guard with 'if x is not None:' before using x.attribute",
     0.80),
    (re.compile(r"ModuleNotFound|ImportError|No module named"),
     "missing import",
     "check: (1) package installed? (2) correct path? (3) circular imports?",
     0.70),
    (re.compile(r"mutable default|default.*argument.*list|default.*argument.*dict"),
     "mutable default argument",
     "use None as default and create fresh list/dict inside the function body",
     0.80),
    (re.compile(r"timezone|naive.*aware|pytz"),
     "comparing naive and aware datetimes",
     "make all datetimes timezone-aware: dt.replace(tzinfo=pytz.UTC)",
     0.70),
    (re.compile(r"struct.*(?:mismatch|unpack|pack|format|size)"),
     "struct format mismatch between writer and reader",
     "ensure struct.pack and struct.unpack use the same format string",
     0.70),
    (re.compile(r"awk.*not found|cannot access|No such file"),
     "awk processing find output with relative paths",
     "use explicit ./ prefix or pipe find output through xargs",
     0.75),
    (re.compile(r"sort.*invalid option|sort.*unrecognized"),
     "sort with wrong delimiter syntax",
     "use: sort -t',' -k3 -rn (single quotes around delimiter)",
     0.70),
    (re.compile(r"tar.*Error|tar.*not found|cannot open"),
     "tar with full paths causing issues",
     "use -C to change directory before archiving: tar -czf -C /srcdir .",
     0.70),
    (re.compile(r"grep.*binary.*match|grep.*is a directory"),
     "grep not filtering file types",
     "use grep -rl --include='*.py' 'pattern' . for recursive search",
     0.65),
    (re.compile(r"GIL|thread.*CPU|no speedup|multiprocessing"),
     "using threading for CPU-bound work",
     "use multiprocessing.Pool for CPU parallelism; threading only for I/O",
     0.80),
    # ── From real session data (reflection JSON, 2026-06-15) ──────
    (re.compile(r"multiple values for keyword argument|got multiple values"),
     "duplicate keyword argument in function call",
     "check the function signature before calling: do not pass kwargs that the wrapper sets internally. Use inspect.signature() or read the docs.",
     0.75),
    (re.compile(r"spawn_depth|max_spawn_depth|nested.*delegat|delegat.*depth|delegat.*nest"),
     "exceeding delegation depth limit",
     "flatten multi-level delegation into a single delegate_task call instead of nesting. Check max_spawn_depth in config before chaining.",
     0.80),
    (re.compile(r"no agent context|not.*callable.*session|tool.*registr.*but.*context"),
     "tool registered but not wired at runtime",
     "verify tool readiness before use: check that the session wired all required providers. If a tool errors immediately, switch to an alternative.",
     0.70),
    (re.compile(r"nonexistent tool|does not exist.*tool|unknown tool.*name|fabricated tool"),
     "referencing a tool that does not exist",
     "check available tools with skills_list or tools_list before calling. Do not guess tool names — verify against the actual toolset.",
     0.75),
    (re.compile(r"bypassed.*chain|skip.*delegat.*chain|wrote.*(?:directly|instead)"),
     "agent bypassed requested delegation chain",
     "follow the user's requested architecture. If the requested chain is impossible, explain why and ask before substituting a different approach.",
     0.65),
    (re.compile(r"tool.*signature.*incorrect|wrong.*parameter.*structur|positional.*instead.*of.*keyword"),
     "calling tool with wrong parameter structure",
     "read the tool schema before calling: check required vs optional fields, parameter names, and types. Use search_files to find the tool definition.",
     0.70),
    (re.compile(r"tool.*schema.*before|inspect.*tool.*signature|mandatory field"),
     "not inspecting tool schema before invocation",
     "always check tool schema for mandatory fields before retrying a failed delegate call. Stop retrying with the same invalid parameters.",
     0.70),
]

# ── Success patterns (from tool args, not errors) ──────────────

_SUCCESS_HEURISTICS: list[tuple[re.Pattern, str, str, float]] = [
    (re.compile(r"tool_name.*write_file|write_file.*read_file|read.*before.*write"),
     "file read before write",
     "always read_file the target path before write_file to avoid guard blocks",
     0.85),
    (re.compile(r"batch_format|format_with_black|ruff format|autoflake"),
     "auto-formatted code before writing",
     "apply formatter before write_file to reduce patch noise",
     0.80),
    (re.compile(r"check.*exist|os\.path\.exists|pathlib.*exists"),
     "existence check before file operation",
     "verify path existence with os.path.exists() before read/write — prevents common errors",
     0.85),
    (re.compile(r"inspect.*signature|schema.*check|check.*required.*field"),
     "tool schema inspection before call",
     "inspect tool schema for mandatory fields before calling — prevents parameter errors",
     0.80),
    (re.compile(r"web_search.*query|search.*recent|search.*current"),
     "web search for time-sensitive data",
     "prefer web_search over training knowledge for recent events, prices, versions",
     0.85),
    (re.compile(r"retry.*delay|backoff|wait.*before.*retry|exponential_backoff"),
     "retry with backoff after transient failure",
     "add delay before retry on transient errors — prevents cascading failures",
     0.80),
    (re.compile(r"verify.*exist|check.*status|ping.*before|health.*check"),
     "precondition check before tool call",
     "verify prerequisites before calling a tool that depends on external state",
     0.75),
    (re.compile(r"browser_navigate.*success|page.*loaded|content.*retrieved"),
     "successful browser navigation with content check",
     "check page content (browser_snapshot) after navigate to verify target reached",
     0.70),
    (re.compile(r"delegate_task.*context|pass.*context|include.*background"),
     "rich context passed to delegate_task",
     "include relevant context when delegating — improves subagent success rate",
     0.75),
    (re.compile(r"read.*first|first.*read|before.*edit|before.*write"),
     "read before edit/write pattern",
     "read_file before edit/write to get current content — prevents guard blocks and patches",
     0.85),
    (re.compile(r"try.*except.*specific|except.*known.*error|catch.*specific"),
     "specific exception handling",
     "catch specific exception types instead of bare except — preserves error context",
     0.80),
]


class LessonExtractor:
    """Extract lessons from tool call events.

    Patterns first, fallback to generic if no match.
    """

    def extract(
        self,
        tool_events: list[dict],
        session_outcome: str = "",
        context: dict | None = None,
    ) -> list[Lesson]:
        """Extract lessons from a list of tool events.

        Args:
            tool_events: List of tool call event dicts.
            session_outcome: 'success', 'failure', or 'partial'.
            context: Optional session context.

        Returns:
            List of Lesson objects.
        """
        lessons: list[Lesson] = []
        seen_fingerprints: set[str] = set()

        for event in tool_events:
            if event.get("type") != "tool_failure":
                continue

            tool_name = event.get("tool", "unknown")
            error_detail = event.get("error_detail", "") or ""
            error_type = event.get("error", "") or ""

            # Try pattern matching
            matched = self._match_heuristic(error_detail + error_type)
            if matched:
                pattern, action, confidence = matched
            else:
                # Generic fallback based on tool
                pattern, action, confidence = self._tool_fallback(tool_name, error_detail)
                if not pattern:
                    continue

            # Dedup by fingerprint
            fp = f"{tool_name}:{pattern[:40]}"
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)

            lesson = Lesson(
                id=f"rsi_{tool_name}_{hash(pattern[:30])}",
                pattern=pattern,
                action=action,
                confidence=confidence,
                frequency=1,
                error_type=error_type,
                tags=["auto", tool_name],
            )
            lessons.append(lesson)

        return lessons

    def _match_heuristic(self, text: str) -> tuple[str, str, float] | None:
        """Match text against heuristic patterns."""
        for pat, pattern_str, action, conf in _HEURISTICS:
            if pat.search(text):
                return pattern_str, action, conf
        return None

    def extract_success(
        self,
        tool_events: list[dict],
    ) -> list[Lesson]:
        """Extract lessons from successful tool calls using success heuristics."""
        lessons: list[Lesson] = []
        seen_fingerprints: set[str] = set()

        for event in tool_events:
            if event.get("type") != "tool_success":
                continue

            tool_name = event.get("tool", "unknown")
            event_input = event.get("input", {})

            if isinstance(event_input, str):
                try:
                    event_input = _json.loads(event_input)
                except (_json.JSONDecodeError, TypeError):
                    event_input = {}
            input_str = _json.dumps(event_input) if isinstance(event_input, dict) else str(event_input)

            matched = self._match_success_heuristic(input_str + " " + tool_name)
            if matched:
                pattern, action, confidence = matched
            else:
                generic = self._success_by_tool(tool_name)
                if generic:
                    pattern, action, confidence = generic
                else:
                    self._increment_consecutive(tool_name)
                    count = self._get_consecutive(tool_name)
                    if count >= 3 and count <= 5:
                        pattern = f"{tool_name} consecutive success"
                        action = f"{tool_name} is working reliably — continue using it"
                        confidence = 0.50 + (count - 3) * 0.10
                    else:
                        continue

            fp = f"success:{tool_name}:{pattern[:40]}"
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)

            lessons.append(Lesson(
                id=f"rsi_success_{tool_name}_{hash(pattern[:30])}",
                pattern=pattern,
                action=action,
                confidence=min(confidence, 1.0),
                frequency=1,
                tags=["success", tool_name],
            ))

        return lessons

    def _match_success_heuristic(self, text: str) -> tuple[str, str, float] | None:
        """Match text against success heuristic patterns."""
        for pat, pattern_str, action, conf in _SUCCESS_HEURISTICS:
            if pat.search(text):
                return pattern_str, action, conf
        return None

    @staticmethod
    def _success_by_tool(tool: str) -> tuple[str, str, float] | None:
        """Generic success pattern when no heuristic matches."""
        generics = {
            "terminal": ("terminal command completed", "verify output before assuming success — check exit_code", 0.55),
            "write_file": ("file written successfully", "prefer write_file over terminal echo for structured content", 0.60),
            "web_search": ("web search returned results", "web search works — use it for current information", 0.70),
            "browser_navigate": ("page loaded successfully", "verify target content with browser_snapshot after navigation", 0.60),
            "read_file": ("file read successfully", "read_file before edit/write to prevent guard blocks", 0.65),
            "delegate_task": ("subagent completed task", "include context and clear goal when delegating", 0.60),
        }
        return generics.get(tool)

    _consecutive: dict[str, int] = {}

    def _increment_consecutive(self, tool: str) -> None:
        self._consecutive[tool] = self._consecutive.get(tool, 0) + 1

    def _get_consecutive(self, tool: str) -> int:
        return self._consecutive.get(tool, 0)

    @staticmethod
    def _tool_fallback(tool: str, error: str) -> tuple[str, str, float]:
        """Fallback heuristic when no pattern matches."""
        fallbacks = {
            "terminal": ("shell command error", f"verify preconditions before running shell commands; error: {error[:60]}", 0.50),
            "read_file": ("file read failure", "ensure file exists before reading with os.path.exists()", 0.50),
            "write_file": ("file write failure", "ensure target directory exists before writing", 0.50),
            "patch": ("patch application failure", "verify target file content matches expected context before patching", 0.45),
            "browser_navigate": ("browser navigation failure", "verify URL is reachable before navigating", 0.45),
            "web_search": ("web search failure", "simplify query and retry with different phrasing", 0.40),
        }
        return fallbacks.get(tool, ("", "", 0.0))

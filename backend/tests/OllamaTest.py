"""
Ollama Wrapper Integration Test Suite
======================================
Run with:  uv run -m tests.OllamaTest

Tests all public functions in DROllamaWrapper.py against the local Ollama
server. Uses Python's built-in `logging` for coloured, timestamped terminal
output — no database involved.

Metrics tracked per test (without third-party libraries):
  • wall-clock latency  (time.perf_counter)
  • response character count
  • tokens estimated   (characters / 4, rough approximation)
  • PASS / FAIL status
"""

import asyncio
import logging
import sys
import time
import json
import tempfile
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _json_safe(obj: Any) -> str:
    """Serialize obj to a JSON string, converting datetime to ISO format."""
    class _Enc(json.JSONEncoder):
        def default(self, o: Any) -> Any:
            if isinstance(o, datetime):
                return o.isoformat()
            # Fallback: convert to string so we never crash
            try:
                return super().default(o)
            except TypeError:
                return str(o)
    return json.dumps(obj, cls=_Enc, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# ── Terminal logger setup ────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

LOG_FORMAT = (
    "%(asctime)s  %(levelname)-8s  %(message)s"
)
logging.basicConfig(
    level=logging.DEBUG,
    format=LOG_FORMAT,
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("OllamaTest")

# Make log levels visually distinct with ANSI colours
_RESET    = "\033[0m"
_BOLD     = "\033[1m"
_GREEN    = "\033[92m"
_YELLOW   = "\033[93m"
_RED      = "\033[91m"
_CYAN     = "\033[96m"
_BLUE     = "\033[94m"
_MAGENTA  = "\033[95m"
_DIM      = "\033[2m"

# ---------------------------------------------------------------------------
# MODEL UNDER TEST
# ---------------------------------------------------------------------------
TEST_MODEL = "qwen3-vl:2b"
TEST_OPTIONS = {"num_ctx": 4096}

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

class TestMetrics:
    def __init__(self, name: str):
        self.name = name
        self._start: float = 0.0
        self.elapsed: float = 0.0
        self.response_chars: int = 0
        self.estimated_tokens: int = 0
        self.passed: bool = False
        self.error: str = ""

    def start(self):
        self._start = time.perf_counter()

    def stop(self, response: Any = None):
        self.elapsed = time.perf_counter() - self._start
        if isinstance(response, str):
            self.response_chars = len(response)
            self.estimated_tokens = max(1, len(response) // 4)
        elif response is not None:
            text = _json_safe(response)
            self.response_chars = len(text)
            self.estimated_tokens = max(1, len(text) // 4)

    def mark_pass(self, response: Any = None):
        self.stop(response)
        self.passed = True

    def mark_fail(self, error: Exception):
        self.stop()
        self.passed = False
        self.error = str(error)

    def report(self):
        status  = f"{_GREEN}{_BOLD}✔ PASS{_RESET}" if self.passed else f"{_RED}{_BOLD}✘ FAIL{_RESET}"
        latency = f"{self.elapsed * 1000:.1f} ms" if self.elapsed < 1 else f"{self.elapsed:.2f} s"
        log.info(
            "%s  %s%-36s%s │ latency: %s%-10s%s │ chars: %s%-7s%s │ ~tokens: %s%-6s%s",
            status,
            _CYAN, self.name, _RESET,
            _YELLOW, latency, _RESET,
            _BLUE, self.response_chars, _RESET,
            _MAGENTA, self.estimated_tokens, _RESET,
        )
        if self.error:
            log.error("         %sError: %s%s", _RED, self.error, _RESET)


# ---------------------------------------------------------------------------
# Separator helpers
# ---------------------------------------------------------------------------

def _section(title: str):
    bar = "─" * 70
    log.info("%s%s%s", _BOLD, bar, _RESET)
    log.info("  %s%s%s", _BOLD + _CYAN, title.upper(), _RESET)
    log.info("%s%s%s", _BOLD, bar, _RESET)


def _subsection(title: str):
    log.info("  %s▶ %s%s", _YELLOW, title, _RESET)


def _print_response(label: str, value: Any):
    """Logs the actual model response beneath a test metric line."""
    if value is None:
        return
    if isinstance(value, str):
        text = value
    else:
        text = _json_safe(value)
    log.info("%s    ┌─ %s ─────────────────────────────────────────%s", _DIM, label, _RESET)
    for line in text.splitlines():
        log.info("%s    │  %s%s", _DIM, line, _RESET)
    log.info("%s    └──────────────────────────────────────────────────%s", _DIM, _RESET)


# ---------------------------------------------------------------------------
# Tiny disposable image (1×1 white JPEG)
# ---------------------------------------------------------------------------

def _create_test_image() -> str:
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (64, 64), color=(135, 206, 235))
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(tmp.name, format="JPEG")
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# ── Test runner ──────────────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

async def run_all_tests():
    # Dynamic import to ensure the circular fix is respected
    try:
        import main.src.utils.llms.ollama.DROllamaWrapper as W
    except ImportError as e:
        log.error("%sImport Error during test initialization: %s%s", _RED, e, _RESET)
        return

    all_metrics: list[TestMetrics] = []
    img_path = _create_test_image()
    log.debug("%sTest image created at: %s%s", _DIM, img_path, _RESET)

    _section("1 · Client Initialisation")
    _subsection("getClient()")
    m = TestMetrics("getClient")
    m.start()
    try:
        client = W.getClient()
        m.mark_pass("Client object returned")
    except Exception as e:
        m.mark_fail(e)
    m.report()
    all_metrics.append(m)

    _subsection("getAsyncClient()")
    m = TestMetrics("getAsyncClient")
    m.start()
    try:
        aclient = W.getAsyncClient()
        m.mark_pass("AsyncClient object returned")
    except Exception as e:
        m.mark_fail(e)
        aclient = None
    m.report()
    all_metrics.append(m)

    if not aclient:
        log.error("%sSkipping async tests because aclient failed to initialize.%s", _RED, _RESET)
        return

    _section("2 · Model Inspection")
    _subsection("getModelList(aclient)")
    models_list = None
    m = TestMetrics("getModelList")
    m.start()
    try:
        models_list = await W.getModelList(aclient)
        m.mark_pass(models_list[:2])
    except Exception as e:
        m.mark_fail(e)
    m.report()
    _print_response("getModelList (first 2)", models_list[:2] if models_list else None)
    all_metrics.append(m)

    _subsection(f"getOllamaModel(aclient, '{TEST_MODEL}')")
    model_info = None
    m = TestMetrics("getOllamaModel")
    m.start()
    try:
        model_info = await W.getOllamaModel(aclient, model_name=TEST_MODEL)
        m.mark_pass(model_info)
    except Exception as e:
        m.mark_fail(e)
    m.report()
    _print_response("getOllamaModel", model_info)
    all_metrics.append(m)

    _subsection(f"checkModelCapabilities(aclient, '{TEST_MODEL}')")
    caps = None
    m = TestMetrics("checkModelCapabilities")
    m.start()
    try:
        caps = await W.checkModelCapabilities(aclient, TEST_MODEL)
        m.mark_pass(caps)
    except Exception as e:
        m.mark_fail(e)
    m.report()
    _print_response("checkModelCapabilities", caps)
    all_metrics.append(m)

    _section("3 · Synchronous Generation")
    _subsection("generateContent() · text")
    m = TestMetrics("generateContent [text]")
    m.start()
    result_gc = None
    try:
        result_gc = W.generateContent("Say 'Test'", "System", TEST_MODEL, None, client, options=TEST_OPTIONS)
        m.mark_pass(result_gc)
    except Exception as e:
        m.mark_fail(e)
    m.report()
    _print_response("generateContent", result_gc)
    all_metrics.append(m)

    _section("4 · Async Generation")
    _subsection("asyncGenerateContent() · text")
    m = TestMetrics("asyncGenerateContent [text]")
    m.start()
    result_agc = None
    try:
        result_agc = await W.asyncGenerateContent("Hi", "System", TEST_MODEL, None, aclient, options=TEST_OPTIONS)
        m.mark_pass(result_agc)
    except Exception as e:
        m.mark_fail(e)
    m.report()
    _print_response("asyncGenerateContent", result_agc)
    all_metrics.append(m)

    _section("5 · Tools")
    def test_tool(msg: str) -> str: return msg
    _subsection("asyncGenerateWithTools()")
    m = TestMetrics("asyncGenerateWithTools")
    m.start()
    resp = None
    try:
        resp = await W.asyncGenerateWithTools("Use tool", "System", TEST_MODEL, aclient, [test_tool], options=TEST_OPTIONS)
        m.mark_pass("Tool call processed")
    except Exception as e:
        m.mark_fail(e)
    m.report()
    if resp is not None:
        content = getattr(getattr(resp, "message", None), "content", None)
        tool_calls = getattr(getattr(resp, "message", None), "tool_calls", None)
        _print_response("asyncGenerateWithTools · content", content)
        _print_response("asyncGenerateWithTools · tool_calls", str(tool_calls) if tool_calls else "(none)")
    all_metrics.append(m)

    _section("6 · Vision")
    _subsection("understandImageWithoutSaving()")
    m = TestMetrics("understandImageWithoutSaving")
    m.start()
    result_img = None
    try:
        result_img = await W.understandImageWithoutSaving(img_path, "Describe", "System", TEST_MODEL, aclient, options=TEST_OPTIONS)
        m.mark_pass(result_img)
    except Exception as e:
        m.mark_fail(e)
    m.report()
    _print_response("understandImageWithoutSaving", result_img)
    all_metrics.append(m)

    _section("7 · Helpers")
    _subsection("_safe_json_loads()")
    m = TestMetrics("_safe_json_loads")
    m.start()
    res = None
    try:
        res = W._safe_json_loads('{"ok": true}')
        m.mark_pass("JSON parsed")
    except Exception as e:
        m.mark_fail(e)
    m.report()
    _print_response("_safe_json_loads", res)
    all_metrics.append(m)

    _section("8 · Planning")
    _subsection("planner()")
    m = TestMetrics("planner")
    m.start()
    last_plan = None
    try:
        async for p in W.planner(TEST_MODEL, "Sys", "User", "Pers", "Add", {"type":"object"}, aclient, 1, options=TEST_OPTIONS):
            last_plan = p
        m.mark_pass("Planner finished")
    except Exception as e:
        m.mark_fail(e)
    m.report()
    _print_response("planner · last iteration", last_plan)
    all_metrics.append(m)

    os.unlink(img_path)

    log.info("\n" + "="*70)
    passed = sum(1 for m in all_metrics if m.passed)
    log.info(f"SUMMARY: {passed}/{len(all_metrics)} PASSED")
    log.info("="*70)

if __name__ == "__main__":
    asyncio.run(run_all_tests())

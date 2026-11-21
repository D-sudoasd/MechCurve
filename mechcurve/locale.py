"""Per-call display language. Sample names, notes, and scientific keys are verbatim."""

import re
from contextlib import contextmanager
from contextvars import ContextVar
from threading import RLock
from .translations import EN

_language = ContextVar("mechcurve_language", default="zh")
_render_lock = RLock()


def language():
    return _language.get()


@contextmanager
def render_context(lang):
    if lang not in ("zh", "en"):
        raise ValueError("lang must be 'zh' or 'en'")
    # Matplotlib has process-global style/font state, including for MCP clients.
    with _render_lock:
        token = _language.set(lang)
        try:
            yield
        finally:
            _language.reset(token)


def tr(message, *values, lang=None):
    template = EN.get(message, message) if (lang or language()) == "en" else message
    return template.format(*values) if values else template


def diagnosis(message):
    """Translate controlled instrument/analysis messages; leave supplied notes intact."""
    if language() != "en" or not message:
        return message
    preliminary = re.fullmatch(
        r"同试验包 S(\d+) 随后完成多周加载；本条仅 (\d+) 点、(\d+) 个完整周，终止于加载途中。疑似初始试运行。",
        message,
    )
    if preliminary:
        later, points, cycles = preliminary.groups()
        return f"Likely preliminary acquisition: {points} points, {cycles} complete cycles, ending during loading. S{later} subsequently completed multiple cycles in the same test package."
    for prefix, translated in (
        ("通道单位无法识别或存在重名列 ", "Unknown unit or duplicate channel: "),
        ("XML 解析失败 ", "XML metadata could not be read: "),
    ):
        if message.startswith(prefix):
            return translated + message[len(prefix) :]
    return ". ".join(
        "; ".join(tr(part) for part in clause.split("；"))
        for clause in message.split("。")
    )

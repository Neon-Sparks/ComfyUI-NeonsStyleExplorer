"""What each executed prompt actually used.

The browser cannot be trusted to pair an image with a style: by the time a run
finishes, the style dropdown may already have moved on (crawl advances it as
each prompt is *queued*, exactly like a seed on control_after_generate). So the
node records, server side, the style it really composed with, keyed by the
prompt id ComfyUI is executing. Auto-gallery then asks the server "what style
was prompt X?" instead of looking at a widget.
"""

import threading
from collections import OrderedDict

# Records are normally consumed the moment a prompt finishes (auto-gallery files
# the image and forgets it), so this map usually holds the single run in flight.
# The cap only bites when nothing consumes them — auto_gallery off, or no browser
# connected — and then the dropped records were never going to be read. It is set
# well above any realistic queue depth because each record is a few hundred bytes.
MAX_RUNS = 512
MAX_PROMPT_CHARS = 2000

_LOCK = threading.RLock()
_RUNS = OrderedDict()  # prompt_id -> {node_id: record}


def current_prompt_id():
    """The prompt ComfyUI is executing right now, or "" outside a run."""
    try:
        from server import PromptServer

        return str(getattr(PromptServer.instance, "last_prompt_id", "") or "")
    except Exception:
        return ""


def record(prompt_id, node_id, **fields):
    """Remember what one node did in one prompt."""
    key = str(prompt_id or "")
    if not key:
        return
    with _LOCK:
        nodes = _RUNS.get(key)
        if nodes is None:
            nodes = {}
            _RUNS[key] = nodes
            while len(_RUNS) > MAX_RUNS:
                _RUNS.popitem(last=False)
        _RUNS.move_to_end(key)
        if isinstance(fields.get("prompt"), str):
            fields["prompt"] = fields["prompt"][:MAX_PROMPT_CHARS]
        nodes[str(node_id or "")] = dict(fields)


def get(prompt_id):
    """Every node record for a prompt, or {} if it is unknown."""
    with _LOCK:
        return dict(_RUNS.get(str(prompt_id or ""), {}))


def latest():
    """(prompt_id, records) for the most recently recorded prompt.

    The fallback for a client that cannot tell us which prompt just finished.
    """
    with _LOCK:
        if not _RUNS:
            return "", {}
        key = next(reversed(_RUNS))
        return key, dict(_RUNS[key])


def forget(prompt_id):
    with _LOCK:
        _RUNS.pop(str(prompt_id or ""), None)


def clear():
    with _LOCK:
        _RUNS.clear()

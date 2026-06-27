from __future__ import annotations
from dataclasses import asdict, is_dataclass
from typing import Any

def to_plain(obj: Any):
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    return obj

def pipeline_result_to_dict(result):
    return to_plain(result)

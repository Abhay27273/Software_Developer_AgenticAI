"""Disk-backed cache for LLM responses keyed by deterministic hashes.

This module keeps previously generated artefacts (plans, test scaffolds,
documentation templates, etc) so we can reuse them instead of calling the LLM
again for the same task and prompt type.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from config import GENERATED_CODE_ROOT

CACHE_ROOT = GENERATED_CODE_ROOT / "cache"

# Ensure the cache root exists on import so callers can immediately store values.
CACHE_ROOT.mkdir(parents=True, exist_ok=True)


def _normalise(value: Optional[str]) -> str:
    return (value or "").strip()


def compute_cache_key(task_id: Optional[str], prompt_type: str) -> str:
    """Return a deterministic hex digest for a (task_id, prompt_type) pair."""
    normalised_task = _normalise(task_id)
    normalised_prompt = _normalise(prompt_type)
    digest_input = f"{normalised_task}:{normalised_prompt}".encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


def _prompt_cache_dir(prompt_type: str) -> Path:
    directory = CACHE_ROOT / _normalise(prompt_type)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def cache_file_path(task_id: Optional[str], prompt_type: str, extension: str = "txt") -> Path:
    """Return the file path for cached artefact content."""
    suffix = extension.lstrip(".") or "txt"
    cache_id = compute_cache_key(task_id, prompt_type)
    return _prompt_cache_dir(prompt_type) / f"{cache_id}.{suffix}"


def metadata_file_path(task_id: Optional[str], prompt_type: str) -> Path:
    cache_id = compute_cache_key(task_id, prompt_type)
    return _prompt_cache_dir(prompt_type) / f"{cache_id}.meta.json"


def load_cached_content(task_id: Optional[str], prompt_type: str, extension: str = "toon") -> Optional[str]:
    """Load cached content if available, otherwise return None. Defaults to .toon for plans."""
    # For plan_generation, try .toon first, then fall back to .txt for legacy
    if prompt_type == "plan_generation":
        toon_path = cache_file_path(task_id, prompt_type, "toon")
        if toon_path.exists():
            return toon_path.read_text(encoding="utf-8")
        # Fallback to .txt for legacy support
        txt_path = cache_file_path(task_id, prompt_type, "txt")
        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8")
        return None
    
    # For other prompt types, use specified extension
    path = cache_file_path(task_id, prompt_type, extension)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def save_cached_content(
    task_id: Optional[str],
    prompt_type: str,
    content: str,
    *,
    extension: str = "txt",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist content and optional metadata for later reuse."""
    cache_path = cache_file_path(task_id, prompt_type, extension)
    cache_path.write_text(content, encoding="utf-8")

    if metadata:
        meta_path = metadata_file_path(task_id, prompt_type)
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def delete_cached_content(task_id: Optional[str], prompt_type: str) -> None:
    """Delete all cached artefacts for a given (task_id, prompt_type) pair.

    This removes both the content file and associated metadata file if present.
    Silently ignores missing files.
    """
    cache_id = compute_cache_key(task_id, prompt_type)
    directory = _prompt_cache_dir(prompt_type)
    for path in directory.glob(f"{cache_id}.*"):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            # Best-effort deletion; ignore any filesystem race conditions
            pass

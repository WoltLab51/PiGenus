"""Persistent memory for PiGenus.

Backed by data/state.json.  A namespaced key-value store that survives
restarts.  The file is structured into four top-level sections::

    {
        "runtime":  {},
        "episodic": {},
        "semantic": {},
        "stats":    {}
    }

The public ``get``/``set``/``all`` API remains backward-compatible: flat
keys written or read via those methods are stored under the ``"runtime"``
section.  Callers that need explicit namespacing can use ``set_in`` /
``get_section``.
"""

import json
import os
from typing import Any

# Resolve data/ relative to this file's parent directory (runtime/)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")

_SECTIONS = ("runtime", "episodic", "semantic", "stats")
_DEFAULT_SECTION = "runtime"


class Memory:
    """Namespaced key-value store that persists to state.json.

    On construction the existing file is loaded (if present), so all
    previously stored values are immediately available after a restart.

    Sections
    --------
    runtime  – general operational keys (default for ``get``/``set``)
    episodic – event/episode records
    semantic – long-term knowledge
    stats    – evaluation scores and counters
    """

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._data: dict = {s: {} for s in _SECTIONS}
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self):
        """Load state from disk; migrate flat format; start fresh on error."""
        if not os.path.exists(STATE_FILE):
            self._data = {s: {} for s in _SECTIONS}
            return
        try:
            with open(STATE_FILE, "r") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError:
            # Preserve the corrupted file for debugging, then start clean.
            corrupt_path = STATE_FILE + ".corrupt"
            try:
                if os.path.exists(corrupt_path):
                    os.remove(corrupt_path)
                os.replace(STATE_FILE, corrupt_path)
            except OSError:
                pass
            self._data = {s: {} for s in _SECTIONS}
            return

        # Guard against valid JSON that is not a dict (e.g. a list or string).
        if not isinstance(raw, dict):
            corrupt_path = STATE_FILE + ".corrupt"
            try:
                if os.path.exists(corrupt_path):
                    os.remove(corrupt_path)
                os.replace(STATE_FILE, corrupt_path)
            except OSError:
                pass
            self._data = {s: {} for s in _SECTIONS}
            return

        # Migration: if the file lacks top-level section keys, it is the old
        # flat format – move all keys into the "runtime" section.
        if not any(k in raw for k in _SECTIONS):
            self._data = {s: {} for s in _SECTIONS}
            self._data[_DEFAULT_SECTION].update(raw)
        else:
            self._data = {s: raw.get(s, {}) for s in _SECTIONS}

    def save(self):
        """Persist current state to disk atomically (survives partial writes)."""
        tmp_path = STATE_FILE + ".tmp"
        with open(tmp_path, "w") as fh:
            json.dump(self._data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, STATE_FILE)

    # ------------------------------------------------------------------
    # Backward-compatible flat API (operates on the "runtime" section)
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return value for *key*, or *default* if absent.

        Searches sections in order: ``runtime`` → ``episodic`` → ``semantic``
        → ``stats``.  The first section that contains *key* wins.  This
        precedence ensures that ``set()`` callers (which always write to
        ``runtime``) are never silently shadowed by section-specific values,
        and that stats written via ``set_in("stats", ...)`` remain accessible
        through the flat API.

        If the same key exists in more than one section (which should be
        avoided by callers), the earlier section takes precedence.
        """
        for section in _SECTIONS:
            if key in self._data[section]:
                return self._data[section][key]
        return default

    def set(self, key: str, value: Any):
        """Store *value* for *key* in the ``runtime`` section and persist."""
        self._data[_DEFAULT_SECTION][key] = value
        self.save()

    def all(self) -> dict:
        """Return a flat copy of all keys across all sections.

        Sections are merged in order: ``runtime``, ``episodic``, ``semantic``,
        ``stats``.  When the same key exists in multiple sections the *later*
        section's value overwrites the earlier one.  Callers that need
        section-isolated data should use :meth:`get_section` instead.
        """
        merged: dict = {}
        for section in _SECTIONS:
            merged.update(self._data[section])
        return merged

    # ------------------------------------------------------------------
    # Namespaced API
    # ------------------------------------------------------------------

    def set_in(self, section: str, key: str, value: Any):
        """Store *value* for *key* in the named *section* and persist.

        Parameters
        ----------
        section:
            One of ``"runtime"``, ``"episodic"``, ``"semantic"``, ``"stats"``.
        key:
            The key within the section.
        value:
            JSON-serialisable value.
        """
        if section not in _SECTIONS:
            raise ValueError(f"Unknown memory section: {section!r}. Choose from {', '.join(_SECTIONS)}")
        self._data[section][key] = value
        self.save()

    def get_section(self, section: str) -> dict:
        """Return a copy of all key-value pairs in *section*.

        Parameters
        ----------
        section:
            One of ``"runtime"``, ``"episodic"``, ``"semantic"``, ``"stats"``.
        """
        if section not in _SECTIONS:
            raise ValueError(f"Unknown memory section: {section!r}. Choose from {', '.join(_SECTIONS)}")
        return dict(self._data[section])

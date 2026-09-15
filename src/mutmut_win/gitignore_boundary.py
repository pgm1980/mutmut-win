"""Hierarchical ``.gitignore`` resolution for staging and basis walks.

``GitignoreBoundary`` lets the staging namespace walk, the staging copy phase
and the run-basis fingerprint prune subtrees that Git itself would never
track.  MBR-2026-09-14-01 showed why this is load-bearing: a correctly
git-ignored ``tests/test_project/.lake`` build tree with 120k files was
enumerated, copied and hashed several times per run, turning run startup into
a 15-60 minute silent crawl.

The boundary mirrors Git's layered ignore semantics for walk pruning:

* every directory may carry its own ``.gitignore`` whose patterns apply
  relative to that directory;
* deeper files take precedence over shallower ones; within one file the last
  matching pattern decides;
* a directory matched as ignored prunes its whole subtree — Git cannot
  re-include files below an excluded directory;
* loading is fail-closed: an unreadable or undecodable ignore file excludes
  nothing and logs a warning.  A walk must never skip a file Git tracks;
  hashing or staging too much is merely cost, skipping tracked files is
  wrong results.

Only project-local ``.gitignore`` files are honoured.
``.git/info/exclude`` and the global ``core.excludesFile`` are deliberate
non-goals: neither belongs to the cloned project bytes a mutation run stages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pathspec import GitIgnoreSpec

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def _candidate(prefix: str, name: str) -> str:
    """Return the walk-root-relative POSIX path for one entry name."""
    return f"{prefix}/{name}" if prefix else name


def _relative_to_base(candidate: str, base: str) -> str | None:
    """Return *candidate* relative to a level base, or None when outside."""
    if not base:
        return candidate
    if candidate == base:
        return ""
    prefix = f"{base}/"
    if candidate.startswith(prefix):
        return candidate[len(prefix) :]
    return None


def _safe_pattern_match(pattern: Any, relative: str) -> Any | None:
    """Evaluate one compiled pattern defensively.

    Pattern objects come from pathspec's gitignore implementation.  Their
    ``match_file`` returns ``None`` (no opinion) or a match result; whether a
    match *excludes* or *re-includes* lives on the pattern's ``include`` flag
    (``False`` marks a ``!`` negation).  A pattern engine failure must degrade
    to "no opinion" instead of breaking the walk.
    """
    try:
        return pattern.match_file(relative)
    except Exception:  # third-party pattern internals must never break a walk
        logger.debug("gitignore pattern evaluation failed for %r", relative, exc_info=True)
        return None


@dataclass(frozen=True)
class _IgnoreLevel:
    """One ``.gitignore`` file bound to the directory providing it."""

    base: str
    patterns: tuple[Any, ...]


def _load_ignore_level(directory: Path, base: str) -> _IgnoreLevel | None:
    """Load one directory's ``.gitignore`` or fail closed to "no opinion".

    A missing file is the normal case and returns ``None`` (no level).
    Unreadable or undecodable files also return ``None`` after a warning so
    the walk stays conservative: such a file can never exclude anything.
    """
    ignore_file = directory / ".gitignore"
    try:
        text = ignore_file.read_bytes().decode("utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning(
            "Ignoring unreadable .gitignore at %s (%s); it excludes nothing",
            ignore_file,
            type(exc).__name__,
        )
        return None

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        spec = GitIgnoreSpec.from_lines(lines)
    except ValueError:
        # pathspec rejects empty pattern lists; a comment-only file carries
        # no rules either way.
        return None
    return _IgnoreLevel(base=base, patterns=tuple(spec.patterns))


class GitignoreBoundary:
    """Immutable, per-directory ignore state carried down a filesystem walk.

    Callers start with :meth:`load` at the walk root, ask
    :meth:`excludes_directory` before descending (pruning whole subtrees) and
    :meth:`excludes_file` for leaf entries.  :meth:`enter` returns the child
    boundary and lazily loads the child directory's own ``.gitignore``.

    Entering a directory that the parent boundary reported as excluded keeps
    the whole subtree excluded: Git never descends into ignored directories,
    so a ``!`` pattern can never re-include files below one.
    """

    __slots__ = ("_directory", "_levels", "_prefix", "_root", "_subtree_excluded")

    def __init__(
        self,
        root: Path,
        directory: Path,
        prefix: str,
        levels: tuple[_IgnoreLevel, ...],
        subtree_excluded: bool = False,
    ) -> None:
        self._root = root
        self._directory = directory
        self._prefix = prefix
        self._levels = levels
        self._subtree_excluded = subtree_excluded

    @classmethod
    def load(cls, project_root: Path) -> GitignoreBoundary:
        """Create the walk-root boundary, honouring the root ``.gitignore``."""
        root_level = _load_ignore_level(project_root, "")
        levels = (root_level,) if root_level is not None else ()
        return cls(project_root, project_root, "", levels)

    def enter(self, name: str) -> GitignoreBoundary:
        """Return the boundary for one child directory.

        Walkers call this only for directories they actually descend into;
        descending into an excluded directory pins the entire subtree as
        excluded regardless of any ``!`` re-inclusion pattern.
        """
        directory = self._directory / name
        prefix = _candidate(self._prefix, name)
        level = _load_ignore_level(directory, prefix)
        levels = (*self._levels, level) if level is not None else self._levels
        return GitignoreBoundary(
            self._root,
            directory,
            prefix,
            levels,
            subtree_excluded=self._subtree_excluded or self.excludes_directory(name),
        )

    def enter_forced(self, name: str) -> GitignoreBoundary:
        """Enter one directory as an explicitly configured entry.

        Explicit configuration mirrors Git's handling of tracked files
        (``git add -f``): ignore decisions from ancestral ignore files do not
        reach into the entry.  Only ignore files at or below the entered
        directory govern its contents, so the level list restarts here.
        """
        directory = self._directory / name
        prefix = _candidate(self._prefix, name)
        level = _load_ignore_level(directory, prefix)
        levels = (level,) if level is not None else ()
        return GitignoreBoundary(self._root, directory, prefix, levels)

    def descend(self, *parts: str) -> GitignoreBoundary:
        """Return the boundary at a relative path using normal enter rules."""
        current = self
        for part in parts:
            if part in {"", "."}:
                continue
            current = current.enter(part)
        return current

    def descend_forced(self, *parts: str) -> GitignoreBoundary:
        """Return the boundary at an explicitly configured relative path.

        ``git add -f`` semantics split by the entry's own status: an entry
        the ancestral ignore rules would exclude is force-tracked as a whole,
        making its subtree immune to those ancestral patterns (only ignore
        files at or below the entry restart governance).  An entry that is
        not itself excluded descends normally, so ignored subtrees *inside*
        it stay pruned — that is the MBR-2026-09-14-01 case: ``tests/`` is
        configured, ``tests/test_project/.lake`` is not.
        """
        relative = [part for part in parts if part not in {"", "."}]
        if not relative:
            return self
        parent = self.descend(*relative[:-1])
        if parent.excludes_directory(relative[-1]):
            directory = self._directory.joinpath(*relative)
            prefix = "/".join(part for part in (self._prefix, *relative) if part)
            level = _load_ignore_level(directory, prefix)
            levels = (level,) if level is not None else ()
            return GitignoreBoundary(self._root, directory, prefix, levels)
        return parent.enter(relative[-1])

    def excludes_directory(self, name: str) -> bool:
        """Return whether Git would ignore the child directory *name*."""
        return self._excludes(_candidate(self._prefix, name), directory=True)

    def excludes_file(self, name: str) -> bool:
        """Return whether Git would ignore the leaf entry *name*."""
        return self._excludes(_candidate(self._prefix, name), directory=False)

    def _excludes(self, candidate: str, *, directory: bool) -> bool:
        """Resolve the layered ignore decision for one candidate path."""
        if self._subtree_excluded:
            return True
        probes = (candidate, f"{candidate}/") if directory else (candidate,)
        for level in reversed(self._levels):
            relative = _relative_to_base(candidate, level.base)
            if relative is None:
                continue
            decision: bool | None = None
            for pattern in level.patterns:
                # Git applies the LAST matching pattern; within one level the
                # pattern order in the file already provides that ordering.
                for probe in probes:
                    if _safe_pattern_match(pattern, probe) is not None:
                        decision = bool(getattr(pattern, "include", True))
            if decision is not None:
                return decision
        return False

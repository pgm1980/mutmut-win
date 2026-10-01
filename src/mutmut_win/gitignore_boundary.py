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
* deeper files take precedence over shallower ones; within one file the
  last matching pattern decides, with Git's directory-marker precedence:
  a negation that hits the candidate only through an ancestor directory
  marker cannot override a real path match, a directory's own end-anchored
  marker counts as a path match, and at equal priority the later pattern
  wins (M-017);
* a directory matched as ignored prunes its whole subtree — Git cannot
  re-include files below an excluded directory;
* loading is fail-closed: an unreadable, undecodable, or invalid ignore
  file excludes nothing itself and suspends inherited rules in its own
  subtree, with a warning.  A walk must never skip a file Git tracks;
  hashing or staging too much is merely cost, skipping tracked files is
  wrong results.

Tracked-index override (M-001): files present in the Git index (tracked,
whether committed or ``git add -f``) are never excluded by ignore patterns.
The index is loaded once per ``load()`` call via ``git ls-files -z --cached
--stage`` and cached per (root, index mtime, index size).  Gitlink entries
(mode 160000, i.e. submodules) count as tracked DIRECTORIES — their path
joins the directory override set, while normal file entries never do.
Without a Git repository the behaviour is unchanged (pure patterns, no
subprocess).  A Git failure with an existing ``.git`` marker logs a warning
and disables pruning entirely for that boundary (``unknown``), ensuring
tracked files are never silently lost.

Only project-local ``.gitignore`` files are honoured.
``.git/info/exclude`` and the global ``core.excludesFile`` are deliberate
non-goals: neither belongs to the cloned project bytes a mutation run stages.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pathspec import GitIgnoreSpec

logger = logging.getLogger(__name__)

#: Name of pathspec's directory-marker capture group (SimpleGiBackend's
#: ``_DIR_MARK``).  Guarded at load time because the whole precedence logic
#: depends on it.
_DIR_MARK = "ps_d"


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


@dataclass(frozen=True)
class _CompiledIgnorePattern:
    """One compiled gitignore pattern with Git's marker-precedence data.

    ``regex`` is pathspec's compiled search pattern; ``anchored`` embeds it
    end-anchored (``(?:...)\\Z``) so a directory probe can prove the pattern
    hits the candidate's OWN trailing slash rather than only an ancestor's.
    ``include`` is ``True`` for positive (ignoring) patterns and ``False``
    for negations (M-017).
    """

    regex: re.Pattern[str]
    anchored: re.Pattern[str]
    include: bool


_dir_marker_guard_done: bool = False


def _verify_dir_marker_support() -> None:
    """Fail loudly when pathspec stops exposing the directory marker.

    The precedence evaluation depends on pathspec's ``ps_d`` capture group;
    silently deciding without it would mis-prune walks.  Guarded once per
    process (M-017).
    """

    global _dir_marker_guard_done
    if _dir_marker_guard_done:
        return
    spec = GitIgnoreSpec.from_lines(["a/"])
    first = next(iter(spec.patterns), None)
    first_regex = getattr(first, "regex", None) if first is not None else None
    if first_regex is None or _DIR_MARK not in first_regex.groupindex:
        raise RuntimeError(
            "pathspec no longer exposes the ps_d directory marker group; "
            "gitignore marker precedence would silently degrade"
        )
    _dir_marker_guard_done = True


def _compile_ignore_patterns(spec: Any) -> tuple[_CompiledIgnorePattern, ...]:
    """Compile pathspec patterns into the precedence-aware representation."""

    compiled: list[_CompiledIgnorePattern] = []
    for pattern in spec.patterns:
        include = getattr(pattern, "include", None)
        if include is None:
            continue  # comment-only pattern carries no rule either way
        try:
            regex = pattern.regex
            anchored = re.compile(f"(?:{regex.pattern})\\Z", regex.flags)
        except Exception:
            logger.debug(
                "gitignore pattern compilation failed for %r",
                getattr(pattern, "regex", pattern),
                exc_info=True,
            )
            continue
        compiled.append(
            _CompiledIgnorePattern(regex=regex, anchored=anchored, include=bool(include))
        )
    return tuple(compiled)


def _match_priority(
    compiled: _CompiledIgnorePattern,
    relative: str,
    *,
    directory: bool,
) -> int | None:
    """Classify one pattern's match on the candidate.

    Returns ``2`` for a real path match, ``1`` for a match that only an
    ancestor directory marker (or, for file candidates, any directory
    marker) provides, and ``None`` when the pattern does not match at all.
    A directory's OWN end-anchored trailing-slash marker counts as a path
    match — that is what keeps whitelist idioms like ``*`` / ``!*/``
    traversable (M-017).
    """

    try:
        has_marker = _DIR_MARK in compiled.regex.groupindex
        match = compiled.regex.search(relative)
        if match is not None and (not has_marker or match.start(_DIR_MARK) == -1):
            return 2
        if directory and has_marker:
            dir_probe = f"{relative}/"
            anchored = compiled.anchored.search(dir_probe)
            if anchored is not None and anchored.end(_DIR_MARK) == len(dir_probe):
                return 2
        if match is not None:
            return 1
        return None
    except Exception:
        logger.debug("gitignore pattern evaluation failed for %r", relative, exc_info=True)
        return None


def _evaluate_level_patterns(
    patterns: tuple[_CompiledIgnorePattern, ...],
    relative: str,
    *,
    directory: bool,
) -> bool | None:
    """Decide one level for one candidate with Git's precedence rule.

    A decision is adopted when the pattern is a positive (ignoring) marker
    match — ancestors propagate exclusion — or when its priority is at least
    the current one; at equal priority the later pattern in the file wins,
    exactly like Git (M-017).
    """

    decision: bool | None = None
    priority = 0
    for compiled in patterns:
        current = _match_priority(compiled, relative, directory=directory)
        if current is None:
            continue
        if (compiled.include and current == 1) or current >= priority:
            decision = compiled.include
            priority = current
    return decision


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
    """One ``.gitignore`` file bound to the directory providing it.

    ``rules_unknown`` marks a level whose file exists but could not be read
    or compiled: the level itself carries no patterns and, in its subtree,
    even inherited ancestor rules are suspended (M-015).
    """

    base: str
    patterns: tuple[_CompiledIgnorePattern, ...] = ()
    rules_unknown: bool = False


def _load_ignore_level(directory: Path, base: str) -> _IgnoreLevel | None:
    """Load one directory's ``.gitignore`` or fail closed to "no opinion".

    A missing file is the normal case and returns ``None`` (no level).
    Unreadable, undecodable, or invalid files produce a ``rules_unknown``
    level after a warning: such a file can never exclude anything itself,
    and its subtree also suspends inherited rules so a broken ``!``
    re-inclusion cannot silently drop files the parent patterns would
    exclude.  The run-basis completeness channel stays with the raw file
    hash (an unreadable file lowers ``complete`` there); a compiled-but-
    invalid file only widens the walk, which is cost, not wrong results.
    UTF-8 files may start with a BOM, which Git skips (``utf-8-sig``).
    """
    ignore_file = directory / ".gitignore"
    try:
        text = ignore_file.read_bytes().decode("utf-8-sig")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning(
            "Ignoring unreadable .gitignore at %s (%s); it excludes nothing "
            "and suspends inherited rules in its subtree",
            ignore_file,
            type(exc).__name__,
        )
        return _IgnoreLevel(base=base, patterns=(), rules_unknown=True)

    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    _verify_dir_marker_support()
    try:
        spec = GitIgnoreSpec.from_lines(lines)
    except ValueError as exc:
        # pathspec raises GitIgnorePatternError (a ValueError subclass) for
        # invalid pattern lines — a lone "!" or a trailing backslash, for
        # example; empty lists cannot reach here because of the filter above.
        logger.warning(
            "Ignoring invalid .gitignore at %s (%s); it excludes nothing "
            "and suspends inherited rules in its subtree",
            ignore_file,
            type(exc).__name__,
        )
        return _IgnoreLevel(base=base, patterns=(), rules_unknown=True)
    return _IgnoreLevel(base=base, patterns=_compile_ignore_patterns(spec))


@dataclass(frozen=True)
class _TrackedIndex:
    """Immutable snapshot of the Git index's tracked paths (M-001).

    ``files`` contains every tracked file path (project-root-relative,
    POSIX separators, case-folded).  ``directories`` contains every
    ancestor-directory prefix of every tracked file plus every gitlink
    (mode 160000) path itself: a gitlink is semantically a tracked
    directory root, so ignore rules cannot prune it (AR-03 / COR-003).
    ``unknown`` marks a Git failure — the boundary then excludes nothing
    (fail-open) to ensure tracked files are never silently pruned.
    """

    files: frozenset[str]
    directories: frozenset[str]
    unknown: bool


#: Process-local cache for the tracked index, keyed by (root, index_mtime, index_size).
_TRACKED_CACHE: dict[tuple[str, int, int], _TrackedIndex] = {}
_TRACKED_CACHE_MAX = 16

#: Environment keys stripped before invoking git (they can redirect the index).
_GIT_ENV_STRIP = frozenset(
    {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_CEILING_DIRECTORIES"}
)

#: Index mode of a gitlink (submodule commit reference): a tracked DIRECTORY.
_GITLINK_MODE = "160000"

#: One ``git ls-files -z --cached --stage`` record:
#: ``<mode> SP <object> SP <stage> (TAB|SP) <path>``.  Current git keeps the
#: tab separator with ``-z``; some versions emit a space instead, so both are
#: accepted.  DOTALL lets a path itself contain newlines (records are already
#: NUL-split); a record that does not match degrades to the plain-path
#: treatment below instead of being dropped.
_STAGE_RECORD = re.compile(
    r"(?P<mode>[0-7]{6}) [0-9a-fA-F]+ [0-3][\t ](?P<path>.+)",
    re.DOTALL,
)


def _fold(path: str) -> str:
    """Case-fold a POSIX path for Windows-insensitive comparison."""
    return path.casefold()


def _find_git_marker(root: Path) -> Path | None:
    """Walk upward from *root* looking for a ``.git`` directory or file."""
    current = root.resolve()
    for candidate in (current, *current.parents):
        marker = candidate / ".git"
        if marker.exists():
            return marker
    return None


def _parse_stage_record(record: str) -> tuple[str | None, str]:
    """Split one ``--stage`` record into ``(mode, path)``.

    Returns ``(None, record)`` for records without stage metadata so the
    caller keeps the conservative plain-path treatment.
    """
    match = _STAGE_RECORD.fullmatch(record)
    if match is None:
        return None, record
    return match.group("mode"), match.group("path")


def _resolve_gitdir_index(marker: Path) -> Path | None:
    """Resolve the index path behind a ``.git`` FILE (AR-04 / COR-004).

    Linked worktrees and submodules carry a ``.git`` file whose single
    ``gitdir: <path>`` line points at their private git directory; the
    per-worktree index lives directly in that git directory.  Relative
    pointers resolve against the directory holding the ``.git`` file.
    Returns ``None`` whenever the pointer cannot be resolved reliably —
    callers must then forgo cache reuse instead of pinning a timeless key.
    """
    try:
        text = marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):  # fmt: skip
        return None
    prefix = "gitdir:"
    if not text.startswith(prefix):
        return None
    gitdir = text[len(prefix) :].strip()
    if not gitdir:
        return None
    pointer = Path(gitdir)
    if not pointer.is_absolute():
        pointer = marker.parent / pointer
    try:
        return pointer.resolve() / "index"
    except OSError:  # pragma: no cover - resolve() on Windows defers OS errors
        return None


def _load_tracked_index(project_root: Path) -> _TrackedIndex:
    """Load the tracked-file set from the Git index (M-001).

    Uses ``git ls-files -z --cached --stage`` (without
    ``--exclude-standard``) to get the full tracked set regardless of ignore
    rules, including each entry's index mode: gitlinks (mode 160000) join
    the directory override set as tracked directory roots, normal entries
    stay files (AR-03 / COR-003).  Repo detection is filesystem-based
    (``.git`` marker search) to avoid false negatives from ``rev-parse``
    errors like "dubious ownership".  Without a ``.git`` marker the result
    is an empty index (pure pattern behaviour).  With a marker but a Git
    failure the result is ``unknown=True`` (excludes nothing).
    """
    marker = _find_git_marker(project_root)
    if marker is None:
        return _TrackedIndex(files=frozenset(), directories=frozenset(), unknown=False)

    # Cache key from the index file's identity when available.  A ``.git``
    # FILE (linked worktree / submodule) contributes no index path by
    # itself: resolve the actual worktree index from its ``gitdir:`` pointer
    # so cache reuse is bound to THAT index's identity (AR-04 / COR-004).
    # Without a trustworthy index identity there is no cache reuse at all —
    # a timeless ``(root, 0, 0)`` key would freeze the first observation for
    # the rest of the process (SEC-002).
    index_path = marker / "index" if marker.is_dir() else _resolve_gitdir_index(marker)
    cache_key: tuple[str, int, int] | None = None
    if index_path is not None and index_path.exists():
        try:
            stat = index_path.stat()
            cache_key = (str(project_root), stat.st_mtime_ns, stat.st_size)
        except OSError:  # pragma: no cover - stat raced with index removal
            cache_key = None
    if cache_key is not None:
        cached = _TRACKED_CACHE.get(cache_key)
        if cached is not None:
            return cached

    env = {k: v for k, v in os.environ.items() if k not in _GIT_ENV_STRIP}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    try:
        result = subprocess.run(  # noqa: S603  # git from PATH; argv list, no shell, env scrubbed
            # S607: "git" from PATH is the project contract (cli.py does the same).
            [  # noqa: S607  # git from PATH per project contract
                "git",
                "-C",
                str(project_root),
                "ls-files",
                "-z",
                "--cached",
                "--stage",
            ],
            capture_output=True,
            timeout=30,
            check=False,
            env=env,
            creationflags=creationflags,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(
            "Git index query failed for %s (%s); gitignore pruning is disabled "
            "for this boundary to avoid losing tracked files",
            project_root,
            type(exc).__name__,
        )
        index = _TrackedIndex(files=frozenset(), directories=frozenset(), unknown=True)
        _cache_tracked(cache_key, index)
        return index

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        logger.warning(
            "git ls-files failed for %s (rc=%d, %s); gitignore pruning is disabled "
            "for this boundary to avoid losing tracked files",
            project_root,
            result.returncode,
            stderr[:200],
        )
        index = _TrackedIndex(files=frozenset(), directories=frozenset(), unknown=True)
        _cache_tracked(cache_key, index)
        return index

    try:
        output = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        logger.warning(
            "git ls-files output for %s is not valid UTF-8; gitignore pruning "
            "is disabled for this boundary",
            project_root,
        )
        index = _TrackedIndex(files=frozenset(), directories=frozenset(), unknown=True)
        _cache_tracked(cache_key, index)
        return index

    files: set[str] = set()
    dirs: set[str] = set()
    for raw_path in output.split("\0"):
        if not raw_path:
            continue
        mode, path = _parse_stage_record(raw_path)
        folded = _fold(path.replace("\\", "/"))
        files.add(folded)
        parts = folded.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
        if mode == _GITLINK_MODE:
            # A gitlink is one tracked path that IS a directory root
            # (submodule commit reference); only its own mode proves that,
            # normal file entries never join the directory set (AR-03).
            dirs.add(folded)

    index = _TrackedIndex(files=frozenset(files), directories=frozenset(dirs), unknown=False)
    _cache_tracked(cache_key, index)
    return index


def _cache_tracked(key: tuple[str, int, int] | None, index: _TrackedIndex) -> None:
    """Store the index in the process-local cache (bounded).

    ``key is None`` means no trustworthy index identity exists (e.g. an
    unresolvable ``.git`` file pointer); caching then would pin this
    observation forever, so the call is a no-op (AR-04).
    """
    if key is None:
        return
    if len(_TRACKED_CACHE) >= _TRACKED_CACHE_MAX:
        _TRACKED_CACHE.clear()
    _TRACKED_CACHE[key] = index


class GitignoreBoundary:
    """Immutable, per-directory ignore state carried down a filesystem walk.

    Callers start with :meth:`load` at the walk root, ask
    :meth:`excludes_directory` before descending (pruning whole subtrees) and
    :meth:`excludes_file` for leaf entries.  :meth:`enter` returns the child
    boundary and lazily loads the child directory's own ``.gitignore``.

    Entering a directory that the parent boundary reported as excluded keeps
    the whole subtree excluded: Git never descends into ignored directories,
    so a ``!`` pattern can never re-include files below one.

    Tracked-index override (M-001): files in the Git index are never
    excluded.  The check runs before ``_subtree_excluded`` and before
    pattern evaluation; ``descend_forced``'s branch decision uses the pure
    pattern verdict (without the override) to preserve ``git add -f``
    semantics for untracked siblings.
    """

    __slots__ = (
        "_directory",
        "_levels",
        "_prefix",
        "_root",
        "_subtree_excluded",
        "_tracked",
    )

    def __init__(
        self,
        root: Path,
        directory: Path,
        prefix: str,
        levels: tuple[_IgnoreLevel, ...],
        subtree_excluded: bool = False,
        tracked: _TrackedIndex | None = None,
    ) -> None:
        self._root = root
        self._directory = directory
        self._prefix = prefix
        self._levels = levels
        self._subtree_excluded = subtree_excluded
        self._tracked = tracked

    @classmethod
    def load(cls, project_root: Path) -> GitignoreBoundary:
        """Create the walk-root boundary, honouring the root ``.gitignore``."""
        root_level = _load_ignore_level(project_root, "")
        levels = (root_level,) if root_level is not None else ()
        tracked = _load_tracked_index(project_root)
        return cls(project_root, project_root, "", levels, tracked=tracked)

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
            tracked=self._tracked,
        )

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

        The branch decision evaluates the PURE pattern verdict at the
        boundary the descent actually reached: intermediate ``.gitignore``
        files load only while descending, so a rule from ``pkg/.gitignore``
        deciding the fate of ``pkg/sub`` is invisible at the walk root
        (AR-02 / COR-002).  The tracked override stays out of the decision:
        a tracked-ignored configured entry keeps the reset branch so
        untracked siblings retain their ``git add -f`` inclusion semantics
        (M-001 counter-review correction).
        """
        relative = [part for part in parts if part not in {"", "."}]
        if not relative:
            return self
        parent = self.descend(*relative[:-1])
        if parent._pure_pattern_excludes(_candidate(parent._prefix, relative[-1]), directory=True):
            directory = self._directory.joinpath(*relative)
            prefix = "/".join(part for part in (self._prefix, *relative) if part)
            level = _load_ignore_level(directory, prefix)
            levels = (level,) if level is not None else ()
            return GitignoreBoundary(self._root, directory, prefix, levels, tracked=self._tracked)
        return parent.enter(relative[-1])

    def excludes_directory(self, name: str) -> bool:
        """Return whether Git would ignore the child directory *name*."""
        return self._excludes(_candidate(self._prefix, name), directory=True)

    def excludes_file(self, name: str) -> bool:
        """Return whether Git would ignore the leaf entry *name*."""
        return self._excludes(_candidate(self._prefix, name), directory=False)

    def _excludes(self, candidate: str, *, directory: bool) -> bool:
        """Resolve the layered ignore decision for one candidate path.

        The tracked-index override (M-001) runs FIRST: a tracked file or a
        directory with tracked content is never excluded, even when patterns
        match.  This preserves the module contract that a walk must never
        skip a file Git tracks.
        """
        if self._tracked is not None:
            if self._tracked.unknown:
                return False
            folded = _fold(candidate)
            if not directory and folded in self._tracked.files:
                return False
            if directory and folded in self._tracked.directories:
                return False
        return self._pure_pattern_excludes(candidate, directory=directory)

    def _pure_pattern_excludes(self, candidate: str, *, directory: bool) -> bool:
        """Pattern-only verdict without the tracked-index override.

        Used by ``descend_forced`` for its branch decision so the tracked
        override cannot change the ``git add -f`` reset semantics.
        """
        if self._subtree_excluded:
            return True
        for level in reversed(self._levels):
            # Git resolves every pattern relative to the directory holding the
            # ignore file.  Matching the walk-root-relative candidate instead
            # would both miss anchored patterns in nested files and let an
            # ancestor path component satisfy an unanchored one.
            relative = _relative_to_base(candidate, level.base)
            if relative is None:
                continue
            if level.rules_unknown:
                # A disturbed level suspends inherited rules for its whole
                # subtree: pruning there could drop files a readable "!"
                # re-inclusion below the broken level would keep (M-015).
                return False
            # Within one level Git applies directory-marker precedence (M-017):
            # a marker-only negation cannot override a real path match, an
            # end-anchored own marker on a directory counts as a path match,
            # and at equal priority the later pattern in the file wins.
            decision = _evaluate_level_patterns(level.patterns, relative, directory=directory)
            if decision is not None:
                return decision
        return False

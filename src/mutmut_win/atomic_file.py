"""Safe atomic publication of byte payloads to workspace files.

The destination is never opened for writing.  Payloads are written to a
random, exclusively-created sibling and then published with ``os.replace``.
This is important for workspace paths: a predictable temporary or backup
name may already be a hardlink or symlink to a file outside the workspace.
"""

from __future__ import annotations

import contextlib
import enum
import os
import secrets
import stat
import time
from pathlib import Path


class UnsafeAtomicWriteError(OSError):
    """Raised when a publication path changes or contains unsafe indirection."""


class _TransientParentInspectionError(UnsafeAtomicWriteError):
    """A parent-identity *observation* failed transiently and may be retried.

    Deliberately narrow (M-069 / Q-30 error taxonomy): only failures of the
    observing calls themselves — ``resolve(strict=True)``/``stat`` errors and
    a parent-vs-resolved identity divergence, both documented to flap under
    Windows filter drivers (MBR-2026-09-14-01 follow-up field data) — use
    this subclass.  Deterministic structural rejections (missing parent,
    link/reparse parent or ancestor, non-directory component) and the
    mid-publication ``expected``-identity tripwire stay on the base class:
    retrying those merely stalls every publication by the full backoff
    ladder before failing with the identical error.  Callers catching
    ``UnsafeAtomicWriteError`` or ``OSError`` remain compatible.
    """


class AtomicReplaceError(PermissionError):
    """The destination entry could not be replaced during atomic publication."""


class AtomicPublicationRaceError(UnsafeAtomicWriteError):
    """A competing publisher replaced the destination before post-validation."""


class AtomicPreconditionError(UnsafeAtomicWriteError):
    """A compare-and-swap precondition failed: the target changed.

    Raised by :func:`atomic_replace_if_unchanged` when the destination's
    current bytes do not match the expected bytes, or when a foreign writer
    recreated the path between displacement and insertion.  Nothing is
    overwritten: the foreign content stays at the destination (or is
    preserved under a displacement path named in the error message).

    Deliberately NOT a subclass of :class:`AtomicReplaceError`
    (PermissionError) so that existing retry loops for
    ``AtomicReplaceError`` never re-run a precondition breach.
    """


class AtomicBackupPromotionError(UnsafeAtomicWriteError):
    """The displaced original could not be promoted to the backup path.

    Raised by :func:`atomic_replace_if_unchanged` AFTER a successful
    compare-and-swap publication, when the displaced original — rebound to
    the leaf identity captured before the displacement — could not be moved
    onto the requested backup path (AR-06 / C-002: a plain rename onto the
    pre-written backup fails under Windows, and suppressing that failure
    used to strand the only recovery copy under an unreported randomly
    named sibling).  Nothing is lost: the displaced file stays exactly
    where the message names it, so callers must surface the location
    instead of reporting a clean backup success.
    """


class AtomicPathLengthError(OSError):
    """A Windows path-length limit blocked the private atomic-write sibling.

    Raised when the operating system rejects the freshly generated sibling
    name with a path-length winerror (3/123/206) and the measured lengths
    actually exceed the NTFS component budget (255 UTF-16 units) or the
    legacy total-path budget (259 UTF-16 units without LongPathsEnabled).
    The message names the target path, both measured lengths and the
    LongPathsEnabled registry option; the original OS error is preserved
    as ``__cause__`` and its errno/winerror are carried on this instance.

    Deliberately NOT an :class:`UnsafeAtomicWriteError`: an over-long name
    is an operability limit, not a safety finding — existing callers
    catching ``OSError`` (staging copy retries, pytest boundary
    preparation) keep working unchanged.
    """


#: Bounded backoff for transient Windows filter-driver interference.  The
#: pytest phase guard republishes its execution sentinel once per test report;
#: under that create/replace churn, antivirus or indexer filters transiently
#: report inconsistent leaf identities or lock the replace target (observed
#: at roughly 1 failure per 5000 publications — MBR-2026-09-14-01 follow-up).
#: Every retry re-runs the complete validation chain, so persistent
#: unsafety still fails closed with the original error taxonomy.
_SIBLING_VALIDATION_RETRY_DELAYS: tuple[float, ...] = (0.002, 0.008, 0.032, 0.064)
_REPLACE_RETRY_DELAYS: tuple[float, ...] = (0.01, 0.02, 0.05, 0.1)
#: Parent capture faces a longer interference window: after thousands of
#: sentinel republications into one runtime directory, filter drivers can
#: hold the directory under scan for seconds at a time (field data:
#: ``resolve(strict=True)`` failed for 5+ attempts on a live directory at
#: ~14 minutes into a phase).  Patience here is safe — capture precedes any
#: publication, so no tripwire can be raced — and the strict resolve itself
#: stays the anti-redirect authority.
_PARENT_CAPTURE_RETRY_DELAYS: tuple[float, ...] = (0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
#: Bounded backoff for transient observation failures of the idempotency
#: probe (M-011).  A momentarily locked or unreadable — but byte-identical —
#: frozen leaf must not be republished just because one observation failed:
#: a republication changes identity/timestamps and trips the frozen staging
#: evidence ("executable staging files changed").  The budget is kept short
#: (sum 1.91 s) and never nests with the parent ladder: the parent identity
#: is captured once per probe call (M-012), so the worst case per ensure
#: call stays at ~15.85 s + 1.91 s.
_IDEMPOTENT_PROBE_RETRY_DELAYS: tuple[float, ...] = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0)


FileIdentity = tuple[int, int]


def _identity(file_stat: os.stat_result) -> FileIdentity:
    return file_stat.st_dev, file_stat.st_ino


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(file_stat, "st_file_attributes", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _checked_parent(path: Path, expected: FileIdentity | None = None) -> FileIdentity:
    """Return a stable parent identity, rejecting symlink/reparse indirection."""
    parent = path.parent.absolute()
    try:
        parent_stat = parent.lstat()
    except OSError as exc:
        raise UnsafeAtomicWriteError(f"cannot inspect atomic-write parent {parent}") from exc

    if (
        not stat.S_ISDIR(parent_stat.st_mode)
        or stat.S_ISLNK(parent_stat.st_mode)
        or _is_reparse_point(parent_stat)
    ):
        raise UnsafeAtomicWriteError(
            f"atomic-write parent must be a real directory, not a link or reparse point: {parent}"
        )

    # Reject indirection in every existing component.  A textual comparison
    # between ``absolute()`` and ``resolve()`` is not a link test on Windows:
    # an ordinary NTFS directory can be addressed through its legitimate 8.3
    # alias while resolving to the long spelling.  Component metadata plus
    # final directory identity distinguishes that alias from a redirect.
    for component in reversed((parent, *parent.parents)):
        try:
            component_stat = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafeAtomicWriteError(
                f"cannot inspect atomic-write parent component {component}"
            ) from exc
        if stat.S_ISLNK(component_stat.st_mode) or _is_reparse_point(component_stat):
            raise UnsafeAtomicWriteError(
                f"atomic-write parent contains link indirection or reparse point: {component}"
            )
        if not stat.S_ISDIR(component_stat.st_mode):
            raise UnsafeAtomicWriteError(
                f"atomic-write parent component is not a directory: {component}"
            )

    try:
        resolved_parent = parent.resolve(strict=True)
        resolved_stat = resolved_parent.stat()
    except OSError as exc:
        raise _TransientParentInspectionError(
            f"cannot resolve atomic-write parent {parent}: "
            f"[errno {exc.errno}, winerror {getattr(exc, 'winerror', None)}] {exc}"
        ) from exc
    if _identity(parent_stat) != _identity(resolved_stat):
        raise _TransientParentInspectionError(
            f"atomic-write parent changed or was redirected: {parent}"
        )

    identity = _identity(parent_stat)
    if expected is not None and identity != expected:
        raise UnsafeAtomicWriteError(f"atomic-write parent changed during publication: {parent}")
    return identity


def _sibling_diagnostics(
    opened_stat: os.stat_result,
    leaf_stat: os.stat_result,
) -> str:
    """Format the one-line field diagnostics for sibling validation exhaustion.

    Field evidence (MBR-2026-09-14-01 follow-up): under filter-driver
    enumeration in child processes, ``os.fstat`` can report one link more
    than the path-view ``lstat`` for the same freshly created inode.  The
    exhaustion diagnosis therefore travels inside the raised
    :class:`UnsafeAtomicWriteError` message — a fixed sink path under the
    shared ``%TEMP%`` followed prepared links onto other files (M-067) and
    grew without bound; the message keeps the same fields (M-067).
    """

    def fields(prefix: str, file_stat: os.stat_result) -> str:
        return (
            f"{prefix}st_mode={file_stat.st_mode}, "
            f"{prefix}st_dev={file_stat.st_dev}, "
            f"{prefix}st_ino={file_stat.st_ino}, "
            f"{prefix}st_nlink={file_stat.st_nlink}, "
            f"{prefix}st_size={file_stat.st_size}, "
            f"{prefix}st_file_attributes={getattr(file_stat, 'st_file_attributes', None)}, "
            f"{prefix}st_reparse_tag={getattr(file_stat, 'st_reparse_tag', None)}"
        )

    return (
        f"pid={os.getpid()}, {fields('opened_', opened_stat)}, "
        f"{fields('leaf_', leaf_stat)}, "
        f"identity_mismatch={_identity(opened_stat) != _identity(leaf_stat)}"
    )


#: NTFS counts file-name components in UTF-16 code units, not Python code
#: points: components above 255 units are rejected with winerror 123/206
#: even when LongPathsEnabled covers the total path (M-010).
_MAX_NTFS_COMPONENT_UTF16 = 255
#: Without LongPathsEnabled, Win32 rejects absolute paths above 259 UTF-16
#: units.  The sibling schema needs '.' + the 51-unit suffix plus one
#: separator on top of the parent, so parents up to 206 units can always
#: carry a sibling (with the embedded name cut to zero if needed); longer
#: parents are the documented residual window, diagnosed via
#: :class:`AtomicPathLengthError` rather than silently worked around.
_MAX_LEGACY_PATH_UTF16 = 259


def _utf16_len(text: str) -> int:
    """Return the length of *text* in UTF-16 code units as NTFS/Win32 count.

    ``surrogatepass`` keeps lone surrogates encodable: Windows file names
    may contain unpaired surrogates (``sys.getfilesystemencodeerrors()`` is
    ``surrogatepass`` under CPython on Windows), and a plain encode would
    raise ``UnicodeEncodeError`` — not an ``OSError`` — for names that
    publish fine today.
    """
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _truncate_to_utf16_budget(text: str, budget: int) -> str:
    """Keep the longest prefix of *text* fitting *budget* UTF-16 units.

    Truncation removes whole code points from the end, so an astral
    character's surrogate pair is never split in half.
    """
    truncated = text[:budget]
    while _utf16_len(truncated) > budget:
        truncated = truncated[:-1]
    return truncated


def _sibling_name(path: Path, token: str) -> str:
    """Build the random sibling name for *path* inside Windows name budgets.

    For names that fit, the schema stays byte-identical to the historic
    ``.{name}.mutmut-atomic-{token}.tmp``.  Only on overflow is the
    EMBEDDED base name shortened — never the random token — first to the
    255-unit NTFS component budget, then to the 259-unit legacy total-path
    budget; the 128-bit token keeps every sibling unique even when the
    embedded name is cut to zero (M-010).
    """
    suffix = f".mutmut-atomic-{token}.tmp"
    component_budget = _MAX_NTFS_COMPONENT_UTF16 - 1 - _utf16_len(suffix)
    parent_units = _utf16_len(os.fspath(path.parent.absolute()))
    path_budget = _MAX_LEGACY_PATH_UTF16 - parent_units - 1 - 1 - _utf16_len(suffix)
    budget = min(component_budget, max(path_budget, 0))
    embedded = _truncate_to_utf16_budget(path.name, budget)
    return f".{embedded}{suffix}"


def _is_path_length_failure(exc: OSError, temp_path: Path) -> bool:
    """Classify *exc* as a Windows path-length rejection of *temp_path*.

    Classification runs strictly over ``winerror`` plus the MEASURED
    lengths — never over errno or the exception type: winerror 3 and 206
    arrive as ``FileNotFoundError`` (errno 2) and only 123 keeps
    ``OSError``/errno 22.  A winerror-3 failure on a path within both
    budgets is a genuine "path not found", not a length rejection, and
    must not be re-labelled.
    """
    winerror = getattr(exc, "winerror", None)
    if winerror not in (3, 123, 206):
        return False
    if _utf16_len(temp_path.name) > _MAX_NTFS_COMPONENT_UTF16:
        return True
    return _utf16_len(os.fspath(temp_path.absolute())) > _MAX_LEGACY_PATH_UTF16


def _open_random_sibling(path: Path) -> tuple[int, Path, FileIdentity]:
    """Open a fresh, exclusively-created and fully validated sibling of *path*.

    The sibling name embeds the target's base name so crash leftovers stay
    attributable to their target; on overflow the embedded name — never
    the random token — is truncated to the Windows name budgets (see
    :func:`_sibling_name`), and an OS length rejection that truncation
    cannot cure is translated into :class:`AtomicPathLengthError` (M-010).
    The returned fd is owned by the caller and closed exactly once on
    every exit route (M-066).
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    collision_attempts_left = 32
    validation_attempts_left = len(_SIBLING_VALIDATION_RETRY_DELAYS) + 1
    while True:
        token = secrets.token_hex(16)
        temp_path = path.with_name(_sibling_name(path, token))
        try:
            fd = os.open(temp_path, flags, 0o600)
        except FileExistsError:
            collision_attempts_left -= 1
            if collision_attempts_left <= 0:
                raise FileExistsError(
                    f"could not allocate a unique atomic-write sibling for {path}"
                ) from None
            continue
        except OSError as exc:
            if _is_path_length_failure(exc, temp_path):
                original_errno = exc.errno if exc.errno is not None else 0
                original_winerror = getattr(exc, "winerror", 0)
                raise AtomicPathLengthError(
                    original_errno,
                    "atomic-write sibling name exceeds the Windows path budgets: "
                    f"target={path} "
                    f"component_utf16={_utf16_len(temp_path.name)}/{_MAX_NTFS_COMPONENT_UTF16}, "
                    f"total_utf16={_utf16_len(os.fspath(temp_path.absolute()))}"
                    f"/{_MAX_LEGACY_PATH_UTF16}; enable LongPathsEnabled "
                    "(HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem) "
                    "or shorten the target path",
                    str(temp_path),
                    original_winerror,
                ) from exc
            raise

        fd_owned = True
        try:
            opened_stat = os.fstat(fd)
            leaf_stat = temp_path.lstat()
            opened_identity = _identity(opened_stat)
            # Handle-derived link counts are not a reliable single-source
            # safety signal on Windows (CX221-071: journals transiently
            # reported zero links; MBR-2026-09-14-01 follow-up field data:
            # ``os.fstat`` transiently reported TWO links for a fresh
            # ``O_EXCL`` inode while the path view reported one, under
            # filter-driver enumeration in child processes).  Exclusive
            # creation, handle/path identity equality, regular-file shape
            # and the path-view link count carry the private-sibling
            # contract; a hardlink attack on this fresh random name would
            # already have failed the ``O_EXCL`` creation above.
            if (
                not stat.S_ISREG(opened_stat.st_mode)
                or stat.S_ISLNK(leaf_stat.st_mode)
                or _is_reparse_point(leaf_stat)
                or opened_identity != _identity(leaf_stat)
                or leaf_stat.st_nlink != 1
            ):
                fd_owned = False
                os.close(fd)
                with contextlib.suppress(OSError):
                    temp_path.unlink()
                validation_attempts_left -= 1
                if validation_attempts_left <= 0:
                    # One-line field diagnosis in the error itself: the
                    # pytest child's truncated output tail shows the last
                    # traceback line reliably, and no file outside the
                    # operation's own directory is ever touched (M-067).
                    raise UnsafeAtomicWriteError(
                        "exclusive atomic-write sibling is not a private regular file: "
                        f"{temp_path} ({_sibling_diagnostics(opened_stat, leaf_stat)})"
                    )
                retry_index = len(_SIBLING_VALIDATION_RETRY_DELAYS) - validation_attempts_left
                time.sleep(_SIBLING_VALIDATION_RETRY_DELAYS[retry_index])
                continue
            return fd, temp_path, opened_identity
        except BaseException:
            # Ownership rule (M-066): the validation-failure branch already
            # closed — and unlinked — its own fd before deciding to retry or
            # fail, and Windows recycles descriptor numbers immediately, so
            # only a still-owned fd may be closed here; a second close could
            # hit a descriptor a concurrent thread just received.  The second
            # unlink attempt stays unconditional: after a failed first
            # unlink the entry may still need cleaning up.
            if fd_owned:
                with contextlib.suppress(OSError):
                    os.close(fd)
            with contextlib.suppress(OSError):
                temp_path.unlink()
            raise


def _checked_temp(path: Path, expected: FileIdentity) -> None:
    try:
        current = path.lstat()
    except OSError as exc:
        raise UnsafeAtomicWriteError(f"atomic-write sibling disappeared: {path}") from exc
    if (
        not stat.S_ISREG(current.st_mode)
        or stat.S_ISLNK(current.st_mode)
        or _is_reparse_point(current)
        or _identity(current) != expected
        or current.st_nlink != 1
    ):
        raise UnsafeAtomicWriteError(f"atomic-write sibling changed before publication: {path}")


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written <= 0:
            raise OSError("short write while publishing atomic byte payload")
        offset += written


def _fsync_parent(path: Path, expected: FileIdentity) -> None:
    """Durably publish the directory entry where the platform supports it."""
    if os.name == "nt":
        # Windows does not expose a portable directory handle through os.open.
        _checked_parent(path, expected)
        return

    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path.parent, flags)
    try:
        if _identity(os.fstat(fd)) != expected:
            raise UnsafeAtomicWriteError(
                f"atomic-write parent changed before directory fsync: {path.parent}"
            )
        os.fsync(fd)
    finally:
        os.close(fd)


def _cleanup_owned_temp(path: Path | None, identity: FileIdentity | None) -> None:
    if path is None or identity is None:
        return
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        return
    if _identity(current) == identity:
        with contextlib.suppress(OSError):
            path.unlink()


class _ProbeResult(enum.Enum):
    """Outcome of one idempotency-probe observation (M-011).

    ``MATCH`` proves a safe, stable, byte-identical leaf; ``MISMATCH``
    proves the strict writer must replace (missing/unsafe leaf or different
    bytes); ``UNVERIFIABLE`` means the observation itself failed and a
    retry may yet prove either.
    """

    MATCH = "match"
    MISMATCH = "mismatch"
    UNVERIFIABLE = "unverifiable"


def _probe_regular_file_bytes(
    path: Path,
    payload: bytes,
    parent_identity: FileIdentity,
) -> tuple[_ProbeResult, OSError | None]:
    """Observe once whether *path* is a safe, stable regular file with *payload*.

    The comparison never follows a link/reparse leaf and never accepts a
    hardlink; both the open handle and the directory entry are revalidated
    before ``MATCH``.  Returns the :class:`_ProbeResult` plus, for
    ``UNVERIFIABLE``, the best available observation error (re-raised by
    the verify-only mode once the retry budget is exhausted).

    Form is judged on the PATH view before identity: Windows lacks a
    functional ``O_NOFOLLOW`` for ``os.open``, so a symlink leaf opens its
    referent and only the directory entry proves the shape.  Handle-view
    deviations (link count, size) with a healthy path view are documented
    transient filter-driver artifacts and therefore ``UNVERIFIABLE``, not
    ``MISMATCH`` — the strict writer must not replace a frozen leaf over a
    flapping handle observation.
    """
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return _ProbeResult.MISMATCH, None
    except OSError as exc:
        # An unreadable/busy leaf neither proves nor disproves that the
        # requested bytes are already published: retry the observation.
        return _ProbeResult.UNVERIFIABLE, exc

    try:
        before = os.fstat(fd)
        try:
            leaf_before = path.lstat()
        except FileNotFoundError:
            return _ProbeResult.MISMATCH, None
        except OSError as exc:
            return _ProbeResult.UNVERIFIABLE, exc

        if (
            not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(leaf_before.st_mode)
            or stat.S_ISLNK(leaf_before.st_mode)
            or _is_reparse_point(leaf_before)
            or leaf_before.st_nlink != 1
            or leaf_before.st_size != len(payload)
        ):
            return _ProbeResult.MISMATCH, None

        before_identity = _identity(before)
        if (
            before.st_nlink != 1
            or before.st_size != len(payload)
            or before_identity != _identity(leaf_before)
        ):
            return _ProbeResult.UNVERIFIABLE, UnsafeAtomicWriteError(
                f"cannot verify idempotent target handle view: {path}"
            )

        received = bytearray()
        while len(received) <= len(payload):
            chunk = os.read(fd, min(64 * 1024, len(payload) + 1 - len(received)))
            if not chunk:
                break
            received.extend(chunk)
        after = os.fstat(fd)
        try:
            leaf_after = path.lstat()
        except OSError as exc:
            # Disappearance mid-probe is re-probed from scratch; a genuinely
            # missing leaf then settles as MISMATCH on the next open.
            return _ProbeResult.UNVERIFIABLE, exc
        try:
            _checked_parent(path, parent_identity)
        except _TransientParentInspectionError as exc:
            # The recheck could not *observe* the parent; a real identity
            # change or structural rejection still raises.
            return _ProbeResult.UNVERIFIABLE, exc

        if (
            not stat.S_ISREG(leaf_after.st_mode)
            or stat.S_ISLNK(leaf_after.st_mode)
            or _is_reparse_point(leaf_after)
            or leaf_after.st_nlink != 1
            or bytes(received) != payload
        ):
            return _ProbeResult.MISMATCH, None
        if (
            _identity(after) != before_identity
            or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns
            or _identity(leaf_after) != before_identity
            or leaf_after.st_size != before.st_size
            or leaf_after.st_mtime_ns != before.st_mtime_ns
        ):
            return _ProbeResult.UNVERIFIABLE, UnsafeAtomicWriteError(
                f"idempotent target changed during probe observation: {path}"
            )
        return _ProbeResult.MATCH, None
    finally:
        os.close(fd)


def _probe_idempotent_leaf(
    path: Path,
    payload: bytes,
    *,
    strict_unverifiable: bool = False,
) -> bool:
    """Run the three-valued probe with bounded retry (M-011).

    The parent identity is captured exactly once through the retry ladder
    (M-012) before the loop, so the two ladders never nest.  ``MATCH``
    returns ``True``; ``MISMATCH`` returns ``False`` so the strict writer
    replaces the leaf; ``UNVERIFIABLE`` is retried through
    ``_IDEMPOTENT_PROBE_RETRY_DELAYS``.  An exhausted budget returns
    ``False`` — or, with *strict_unverifiable*, re-raises the last
    observation cause: post-snapshot callers that must never republish
    frozen staging content fail with the real error instead.
    """
    parent_identity = _capture_parent_identity(path)
    last_cause: OSError | None = None
    delays = (0.0, *_IDEMPOTENT_PROBE_RETRY_DELAYS)
    for delay in delays:
        if delay:
            time.sleep(delay)
        result, cause = _probe_regular_file_bytes(path, payload, parent_identity)
        if result is _ProbeResult.MATCH:
            return True
        if result is _ProbeResult.MISMATCH:
            return False
        last_cause = cause
    if strict_unverifiable and last_cause is not None:
        raise last_cause
    return False


def _regular_file_matches_bytes(path: Path, payload: bytes) -> bool:
    """Return whether *path* is one safe, stable regular file with *payload*.

    Stable test seam: signature ``(path, payload) -> bool``.  Internally the
    three-valued probe (:func:`_probe_regular_file_bytes`) retries transient
    observation failures through a bounded backoff; only a proven ``MATCH``
    returns ``True`` — a link, hardlink or reparse leaf is never accepted,
    and unprovable observations never fabricate a match.
    """
    return _probe_idempotent_leaf(path, payload)


def _atomic_write_attempt(
    path: Path,
    payload: bytes,
    parent_identity: FileIdentity,
    mode: int | None,
    timestamps_ns: tuple[int, int] | None,
) -> None:
    """Run one complete publication attempt with a fresh private sibling."""
    fd: int | None = None
    temp_path: Path | None = None
    temp_identity: FileIdentity | None = None
    try:
        fd, temp_path, temp_identity = _open_random_sibling(path)
        _checked_parent(path, parent_identity)
        if mode is not None:
            temp_path.chmod(mode, follow_symlinks=False)
            _checked_temp(temp_path, temp_identity)
        _write_all(fd, payload)
        if timestamps_ns is not None:
            if os.utime in os.supports_follow_symlinks:
                os.utime(temp_path, ns=timestamps_ns, follow_symlinks=False)
            else:
                # Windows exposes neither fd-relative utime nor the
                # follow_symlinks switch. The leaf is random, exclusively
                # created and still open; the identity check below remains
                # the portable substitution guard.
                os.utime(temp_path, ns=timestamps_ns)
            _checked_temp(temp_path, temp_identity)
        os.fsync(fd)
        os.close(fd)
        fd = None

        _checked_parent(path, parent_identity)
        _checked_temp(temp_path, temp_identity)
        try:
            temp_path.replace(path)
        except PermissionError as exc:
            raise AtomicReplaceError(f"could not replace atomic-write leaf {path}: {exc}") from exc
        temp_path = None

        try:
            published = path.lstat()
        except OSError as exc:
            raise UnsafeAtomicWriteError(
                f"published atomic-write leaf disappeared: {path}"
            ) from exc
        if _identity(published) != temp_identity:
            raise AtomicPublicationRaceError(f"published atomic-write identity mismatch: {path}")
        _fsync_parent(path, parent_identity)
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        _cleanup_owned_temp(temp_path, temp_identity)


def _capture_parent_identity(path: Path) -> FileIdentity:
    """Capture the parent identity, retrying only transient observation failures.

    Retried (as :class:`_TransientParentInspectionError`) and only those:

    - ``resolve(strict=True)``/``stat`` errors on the parent — Windows
      filter drivers can make a healthy parent momentarily unresolvable
      (MBR-2026-09-14-01 follow-up field data: ``resolve(strict)`` failed
      for a live runtime directory mid-phase);
    - a parent-vs-resolved identity divergence, which is known to flap
      for the same reason while both ``lstat`` views stay healthy.

    Every deterministic structural rejection — missing or uninspectable
    parent, link/reparse parent or ancestor, non-directory component —
    and the mid-publication ``expected``-identity tripwire propagate
    immediately with the base-class error: they fail identically on every
    attempt, so retrying them would only stall the caller by the full
    backoff ladder (M-069).  The capture precedes any publication, so
    retrying it cannot race or weaken a publication tripwire; a genuinely
    redirected or linked parent still fails closed.

    Callers: the strict writer (:func:`atomic_write_bytes`), the
    compare-and-swap path and — since M-012 — the idempotent probe behind
    :func:`ensure_atomic_bytes`; the same read-only "capture before any
    publication" justification covers all of them.
    """
    delays = (0.0, *_PARENT_CAPTURE_RETRY_DELAYS)
    for index, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        try:
            return _checked_parent(path)
        except _TransientParentInspectionError:
            if index == len(delays) - 1:
                raise
    raise AssertionError("unreachable: the retry loop always returns or raises")


def atomic_write_bytes(
    path: Path,
    payload: bytes,
    *,
    mode: int | None = None,
    timestamps_ns: tuple[int, int] | None = None,
) -> None:
    """Atomically write bytes without ever opening an existing leaf for writing.

    The immediate parent must already exist and must not contain symlink or
    reparse-point indirection.  ``mode`` and ``timestamps_ns`` are applied to
    the private sibling before publication, which lets atomic copies preserve
    the stat fields used by staging freshness checks.

    Transient Windows filter-driver interference is absorbed at three narrow
    points, each revalidating completely: parent-identity capture, private
    sibling creation, and the final replace (MBR-2026-09-14-01 follow-up).
    Every other condition — publication races, mid-publication parent or
    sibling substitution — fails immediately with the original taxonomy;
    retrying those would weaken the attack tripwires.  A sibling name that
    no longer fits the Windows component or total-path budgets after
    truncation fails as :class:`AtomicPathLengthError` naming the measured
    lengths (M-010).
    """
    path = Path(path)
    parent_identity = _capture_parent_identity(path)
    delays = (0.0, *_REPLACE_RETRY_DELAYS)
    for index, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        try:
            _atomic_write_attempt(path, payload, parent_identity, mode, timestamps_ns)
            return
        except AtomicReplaceError:
            if index == len(delays) - 1:
                raise
    raise AssertionError("unreachable: the retry loop always returns or raises")


def ensure_atomic_bytes(
    path: Path,
    payload: bytes,
    *,
    replace_unverifiable: bool = True,
) -> None:
    """Idempotently publish *payload*, accepting only an identical safe winner.

    :func:`atomic_write_bytes` deliberately detects when another writer
    replaces its just-published inode.  That is the correct default for
    independent writers, but deterministic generated files can have many
    concurrent publishers with byte-identical payloads.  This helper first
    avoids a redundant replacement and, if a strict publication loses a race,
    treats the operation as successful only when the winning leaf is a safe,
    stable regular file containing the exact requested bytes.  A different or
    unverifiable winner preserves the original failure.

    The idempotency probe retries transient observation failures through a
    bounded backoff (M-011), so a momentarily locked — but byte-identical —
    frozen leaf is never republished: a republication would change
    identity/timestamps and trip the frozen staging evidence.  Callers
    publishing into already-frozen staging (guard/collection/stats plugins
    after the evidence snapshot) pass ``replace_unverifiable=False``: when
    the probe budget is exhausted without a verdict, the real observation
    error propagates instead of a blind replacement, keeping the fatal
    ``OSError`` channel unchanged.
    """
    path = Path(path)
    if replace_unverifiable:
        if _regular_file_matches_bytes(path, payload):
            return
    elif _probe_idempotent_leaf(path, payload, strict_unverifiable=True):
        return
    try:
        atomic_write_bytes(path, payload)
    except (
        AtomicPublicationRaceError,
        AtomicReplaceError,
    ):
        if _regular_file_matches_bytes(path, payload):
            return
        raise


def create_exclusive_random_bytes(
    directory: Path,
    payload: bytes,
    *,
    prefix: str,
    suffix: str,
) -> tuple[Path, FileIdentity]:
    """Create and publish one randomly named file without replacing any leaf.

    The returned path and identity describe a private, regular file created
    with ``O_EXCL`` in a real, identity-checked directory. Unlike
    :func:`atomic_write_bytes`, this helper never calls ``replace``: a
    pre-existing user path is therefore never an eligible publication target.

    A validation failure of the freshly created file is retried through
    ``_SIBLING_VALIDATION_RETRY_DELAYS`` (fresh random name, fresh
    ``O_EXCL`` creation, full revalidation) — a budget kept strictly
    separate from the 32-attempt collision budget, whose exhaustion still
    ends in ``FileExistsError`` (M-013).
    """
    if not prefix or Path(prefix).name != prefix or Path(suffix).name != suffix:
        raise ValueError("exclusive random file prefix/suffix must be plain names")

    directory = Path(directory)
    probe = directory / f"{prefix}probe{suffix}"
    parent_identity = _checked_parent(probe)
    if parent_identity[0] < 0 or parent_identity[1] <= 0:
        raise UnsafeAtomicWriteError(
            f"exclusive random-file parent has no stable device/inode identity: {directory}"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)

    collision_attempts_left = 32
    validation_attempts_left = len(_SIBLING_VALIDATION_RETRY_DELAYS) + 1
    while True:
        path = directory / f"{prefix}{secrets.token_hex(16)}{suffix}"
        fd: int | None = None
        identity: FileIdentity | None = None
        keep = False
        try:
            try:
                fd = os.open(path, flags, 0o600)
            except FileExistsError:
                collision_attempts_left -= 1
                if collision_attempts_left <= 0:
                    raise FileExistsError(
                        f"could not allocate a unique exclusive file in {directory}"
                    ) from None
                continue

            opened = os.fstat(fd)
            identity = _identity(opened)
            leaf = path.lstat()
            # Handle-derived link counts are deliberately NOT part of the
            # rejection condition — the same reasoning as in
            # ``_open_random_sibling``: Windows filter drivers transiently
            # report zero or two links for a fresh ``O_EXCL`` inode
            # (CX221-071; MBR-2026-09-14-01 follow-up field data) while the
            # path view stays at one.  Exclusive creation, handle/path
            # identity equality, regular-file shape and the path-view link
            # count carry the private-file contract; a hardlink attack on
            # this fresh random name would already have failed the
            # ``O_EXCL`` creation above (M-013).
            if (
                not stat.S_ISREG(opened.st_mode)
                or stat.S_ISLNK(leaf.st_mode)
                or _is_reparse_point(leaf)
                or identity[0] < 0
                or identity[1] <= 0
                or identity != _identity(leaf)
                or leaf.st_nlink != 1
            ):
                # Ownership is released before the close so an OSError from
                # the close itself never triggers a second close in the
                # finally.  The own fresh ``O_EXCL`` entry is unlinked BY
                # NAME — a name nobody else can have created — because a
                # handle/path identity flap would defeat an
                # identity-checked cleanup and leave the entry behind.
                owned_fd = fd
                fd = None
                os.close(owned_fd)
                with contextlib.suppress(OSError):
                    path.unlink()
                identity = None
                validation_attempts_left -= 1
                if validation_attempts_left <= 0:
                    raise UnsafeAtomicWriteError(
                        f"exclusive random file is not a private regular file: {path}"
                    )
                retry_index = len(_SIBLING_VALIDATION_RETRY_DELAYS) - validation_attempts_left
                time.sleep(_SIBLING_VALIDATION_RETRY_DELAYS[retry_index])
                continue

            _checked_parent(path, parent_identity)
            _write_all(fd, payload)
            os.fsync(fd)
            os.close(fd)
            fd = None
            _checked_parent(path, parent_identity)
            _checked_temp(path, identity)
            _fsync_parent(path, parent_identity)
            keep = True
            return path, identity
        finally:
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)
            if not keep:
                _cleanup_owned_temp(path, identity)


def atomic_copy_file(source: Path, destination: Path) -> None:
    """Copy a regular file through the safe atomic publication path.

    The source is read through one open handle and checked for identity/size/
    mtime changes before its bytes are published.  Mode and timestamps are
    applied to the private sibling, never to an existing destination leaf.
    """
    source = Path(source)
    with source.open("rb") as source_file:
        before = os.fstat(source_file.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise OSError(f"atomic copy source is not a regular file: {source}")
        payload = source_file.read()
        after = os.fstat(source_file.fileno())

    if (
        _identity(before) != _identity(after)
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(payload) != after.st_size
    ):
        raise OSError(f"atomic copy source changed while it was being read: {source}")

    atomic_write_bytes(
        destination,
        payload,
        mode=stat.S_IMODE(after.st_mode),
        timestamps_ns=(after.st_atime_ns, after.st_mtime_ns),
    )


def _displacement_sibling(path: Path) -> Path:
    """Return a random displacement sibling that never ends in ``.py``.

    The name starts with the source name (findable after a crash) and ends
    in ``.mutmut-displaced`` so :func:`file_setup.walk_source_files` never
    picks it up as a Python source.
    """
    import secrets

    suffix = secrets.token_hex(8)
    return path.with_name(f".{path.name}.{suffix}.mutmut-displaced")


def atomic_replace_if_unchanged(
    path: Path,
    payload: bytes,
    *,
    expected: bytes,
    mode: int | None = None,
    backup_path: Path | None = None,
) -> bool:
    """Compare-and-swap publication: replace *path* only if it holds *expected*.

    Protocol (M-005):

    1. Write a private temp sibling with *payload* (existing atomic
       machinery).  The sibling is owned until publication: every failure
       on any later stage — write, fsync, temp/parent revalidation,
       displacement or insertion — releases it through one identity-bound
       cleanup guard, while a foreign inode replacement at the temp name is
       never deleted (AR-07 / COR-005 + PERF-001).
    2. Check the parent; capture the target's identity via ``lstat``.
    3. Rename the target to a private displacement sibling (``os.rename``,
       NOT ``replace`` — fails if another process recreated it).
    4. Verify the displaced file: identity must match the captured identity
       AND content must match *expected*.
    5. Rename the temp into place (``os.rename`` — a ``FileExistsError``
       means a foreign writer recreated the path; their file stays).
    6. Post-publication identity check.
    7. Promote the displaced file to *backup_path* — rebound to the leaf
       identity captured before the displacement and moved with an atomic
       replace, because the backup side usually already exists (callers
       like apply pre-write it; a plain rename onto an existing file fails
       under Windows).  A writer that still holds the displaced inode open
       through ``FILE_SHARE_DELETE`` keeps its bytes: they travel with the
       promoted inode into the named backup (AR-06 / C-002).  Without a
       backup path the displaced file stays at the displacement path — it
       is NEVER deleted.

    Returns:
        ``True`` on success, ``False`` if the current bytes already equal
        *payload* (no write needed).

    Raises:
        AtomicPreconditionError: The target's current bytes differ from
            *expected*, or a foreign writer interfered.  Nothing is
            overwritten; foreign content stays at *path* or under a
            displacement path named in the error.
        UnsafeAtomicWriteError: The parent contains unsafe indirection.
        AtomicPublicationRaceError: Post-publication identity mismatch;
            the original stays under a displacement path named in the error.
        AtomicBackupPromotionError: The publication succeeded but the
            displaced original could not be promoted onto *backup_path*;
            the original is preserved at the displacement path named in
            the error message (never silently stranded).
    """
    path = Path(path)
    parent_identity = _capture_parent_identity(path)

    # Read the current bytes to check whether a swap is needed.
    try:
        current = path.read_bytes()
    except FileNotFoundError:
        msg = f"compare-and-swap target does not exist: {path}"
        raise AtomicPreconditionError(msg) from None
    except OSError as exc:
        msg = f"cannot read compare-and-swap target {path}: {exc}"
        raise AtomicPreconditionError(msg) from exc

    if current == payload:
        return False
    if current != expected:
        msg = f"compare-and-swap target bytes differ from expected: {path}"
        raise AtomicPreconditionError(msg)

    # Step 1: write the private temp sibling with the new payload.  The
    # sibling is OWNED from creation until its publication (or documented
    # promotion): one identity-bound cleanup guard covers the whole
    # preparation and displacement section, so a failure at the write,
    # fsync, temp/parent revalidation or any later stage releases the
    # private sibling.  The guard is identity-bound by design (AR-07 /
    # COR-005 + PERF-001): a foreign inode replacement at the temp name
    # survives, and the displaced original / promoted backup live at
    # different paths, so the recovery side is never touched.
    fd, temp_path, temp_identity = _open_random_sibling(path)
    try:
        try:
            if mode is not None:
                os.fchmod(fd, mode)
            _write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        _checked_temp(temp_path, temp_identity)
        _checked_parent(path, parent_identity)

        # Step 2: capture the target's identity.
        try:
            target_stat = path.lstat()
        except OSError as exc:
            msg = f"cannot inspect compare-and-swap target {path}: {exc}"
            raise AtomicPreconditionError(msg) from exc
        target_identity = _identity(target_stat)

        # Step 3: displace the target (os.rename, NOT replace).
        displaced_path = _displacement_sibling(path)
        try:
            path.rename(displaced_path)
        except OSError as exc:
            msg = f"cannot displace compare-and-swap target {path}: {exc}"
            raise AtomicPreconditionError(msg) from exc

        # Step 4: verify the displaced file.
        try:
            displaced_stat = displaced_path.lstat()
            displaced_content = displaced_path.read_bytes()
        except OSError as exc:
            # The displacement succeeded but we cannot verify it — attempt
            # restoration, then fail closed.
            with contextlib.suppress(OSError):
                displaced_path.rename(path)
            msg = f"cannot verify displaced file {displaced_path}: {exc}; restoration attempted"
            raise AtomicPreconditionError(msg) from exc

        if _identity(displaced_stat) != target_identity or displaced_content != expected:
            # The file changed between identity capture and displacement —
            # restore it and fail closed.  The message must reflect the ACTUAL
            # recovery outcome: a failed restoration keeps the bytes under the
            # displacement path and says so (AR-06 / C-002).
            try:
                displaced_path.rename(path)
            except OSError as restore_exc:
                msg = (
                    f"compare-and-swap target changed between check and displacement: {path}; "
                    f"restoration failed ({restore_exc}); "
                    f"the changed content is preserved at {displaced_path}"
                )
                raise AtomicPreconditionError(msg) from restore_exc
            msg = (
                f"compare-and-swap target changed between check and displacement: {path}; "
                f"the changed content was restored to {path}"
            )
            raise AtomicPreconditionError(msg)

        # Step 5: insert the temp (os.rename — FileExistsError is fail-closed).
        try:
            temp_path.rename(path)
        except FileExistsError:
            # A foreign writer recreated the path while it was displaced.
            # Their file stays; the displaced original is preserved.
            msg = (
                f"a foreign writer recreated {path} during displacement; "
                f"the original content is preserved at {displaced_path}"
            )
            raise AtomicPreconditionError(msg) from None
        except OSError as exc:
            # Attempt restoration of the displaced file.
            with contextlib.suppress(OSError):
                displaced_path.rename(path)
            msg = (
                f"cannot insert replacement at {path}: {exc}; "
                f"original content preserved at {displaced_path}"
            )
            raise AtomicPreconditionError(msg) from exc

        # Step 6: post-publication identity check.  The displaced original is
        # still un-promoted here, so every publication failure names the exact
        # recovery location (AR-06 / C-002).
        try:
            published_stat = path.lstat()
        except OSError as exc:
            msg = (
                f"cannot verify published file {path}: {exc}; "
                f"the original is preserved at {displaced_path}"
            )
            raise AtomicPublicationRaceError(msg) from exc
        if _identity(published_stat) != temp_identity:
            msg = (
                f"published file identity mismatch at {path}; "
                f"the original is preserved at {displaced_path}"
            )
            raise AtomicPublicationRaceError(msg)

        # Step 7 (AR-06 / C-002): promote the displaced original into the KNOWN
        # backup path, rebound to the leaf identity captured before the
        # displacement.  The backup side usually already exists (apply pre-writes
        # it), so promotion is an atomic replace — the suppressed plain rename
        # used to strand the displaced inode under an unreported random sibling
        # name while the stale backup survived.  A FILE_SHARE_DELETE writer that
        # still holds the inode keeps its bytes: they travel with the promoted
        # inode into the named backup.  A promotion failure NEVER deletes the
        # displaced file; it fails loudly with the surviving location instead.
        if backup_path is not None:
            backup_path = Path(backup_path)
            try:
                displaced_now = displaced_path.lstat()
                if _identity(displaced_now) != target_identity:
                    raise UnsafeAtomicWriteError(
                        f"displaced original was replaced before backup promotion: {displaced_path}"
                    )
                _checked_parent(displaced_path, parent_identity)
                displaced_path.replace(backup_path)
                promoted = backup_path.lstat()
                if _identity(promoted) != target_identity:
                    raise UnsafeAtomicWriteError(
                        f"backup promotion lost the displaced original identity: {backup_path}"
                    )
            except OSError as exc:
                msg = (
                    f"the replaced original could not be promoted to the backup "
                    f"{backup_path} ({exc}); the original is preserved at {displaced_path}"
                )
                raise AtomicBackupPromotionError(msg) from exc

        _fsync_parent(path, parent_identity)
        return True
    finally:
        # Identity-bound ownership guard (AR-07): after a successful
        # insertion the temp entry no longer exists (or holds a foreign
        # inode), so this is a no-op; on every failure path it releases the
        # still-owned private sibling.  Swallowed unlinks keep the original
        # error primary.
        _cleanup_owned_temp(temp_path, temp_identity)

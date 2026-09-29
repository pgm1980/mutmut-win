"""Editable PEP 610 URL decoding regressions (AP-11 / M-060).

``_editable_source_path`` must percent-decode the path component of a
``direct_url.json`` file URL exactly once: ``urllib.request.url2pathname``
already decodes percent escapes under CPython on Windows, so an additional
``urllib.parse.unquote`` re-decodes literal ``%HH`` sequences in the source
location (``dep%20copy`` became ``dep copy``) and bound a neighboring tree
instead of the installed one — or failed the strict coverage resolution
altogether.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

import mutmut_win.stats as stats_module
from mutmut_win.stats import _editable_source_path, _installed_distribution_basis
from tests.unit.test_dependency_basis_220 import _FakeDistribution

if TYPE_CHECKING:
    from importlib.metadata import Distribution

# A single Windows path segment: no separators or reserved characters, no
# trailing dots/spaces, no DOS device names. '%' stays in — the whole point.
_SEGMENT_CHARACTERS = st.characters(
    codec="utf-8",
    exclude_categories=("Cs", "Cc"),
    exclude_characters='<>:"/|?*' + chr(92),
)
_segment_names = st.text(alphabet=_SEGMENT_CHARACTERS, min_size=1, max_size=20).filter(
    lambda name: name == name.strip(" .") and name.upper() not in {"CON", "PRN", "AUX", "NUL"}
)


def _editable_direct_url(url: str) -> str:
    return json.dumps({"url": url, "dir_info": {"editable": True}}, separators=(",", ":"))


def test_percent_escaped_space_name_round_trips_undecoded() -> None:
    direct_url = _editable_direct_url(Path("C:/deps/demo%20repo").as_uri())

    assert _editable_source_path(direct_url) == Path("C:/deps/demo%20repo")


def test_percent_escaped_separator_name_round_trips_undecoded() -> None:
    direct_url = _editable_direct_url(Path("C:/jenkins/ws/feature%2Fbranch/pkg").as_uri())

    assert _editable_source_path(direct_url) == Path("C:/jenkins/ws/feature%2Fbranch/pkg")


def test_localhost_netloc_still_resolves_to_local_path() -> None:
    direct_url = _editable_direct_url("file://localhost/C:/w/demo-editable")

    assert _editable_source_path(direct_url) == Path("C:/w/demo-editable")


def test_non_file_scheme_is_rejected() -> None:
    direct_url = _editable_direct_url("https://example.com/demo-editable")

    assert _editable_source_path(direct_url) is None


@pytest.mark.parametrize(
    "direct_url",
    [
        pytest.param("{not json", id="invalid-json"),
        pytest.param(json.dumps(["demo"]), id="payload-not-an-object"),
        pytest.param(
            json.dumps({"url": "file:///C:/w/demo"}),
            id="dir-info-missing",
        ),
        pytest.param(
            json.dumps({"url": "file:///C:/w/demo", "dir_info": "editable"}),
            id="dir-info-not-an-object",
        ),
        pytest.param(
            json.dumps({"url": "file:///C:/w/demo", "dir_info": {"editable": False}}),
            id="not-editable",
        ),
        pytest.param(
            json.dumps({"dir_info": {"editable": True}}),
            id="url-missing",
        ),
        pytest.param(
            json.dumps({"url": 42, "dir_info": {"editable": True}}),
            id="url-not-a-string",
        ),
        pytest.param(
            json.dumps({"url": "file://server/C:/w/demo", "dir_info": {"editable": True}}),
            id="foreign-netloc",
        ),
        pytest.param(
            json.dumps({"url": "http://localhost/C:/w/demo", "dir_info": {"editable": True}}),
            id="non-file-scheme-with-local-netloc",
        ),
    ],
)
def test_preconditions_reject_non_local_non_editable_payloads(direct_url: str) -> None:
    assert _editable_source_path(direct_url) is None


@example("a;b#c?d")
@example("100%done")
@example("x%41y")
@example("feature%2Fbranch")
@example("demo%20repo")
@given(name=_segment_names)
def test_path_as_uri_round_trips_through_editable_source_path(name: str) -> None:
    expected = Path("C:/w") / name

    assert _editable_source_path(_editable_direct_url(expected.as_uri())) == expected


def test_distribution_basis_binds_percent_named_editable_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A drift in ``dep%20copy`` must reach the digest, not the ``dep copy`` neighbor."""

    project = tmp_path / "project"
    distribution_root = tmp_path / "site-packages"
    editable_root = tmp_path / "dep%20copy"
    neighbor_root = tmp_path / "dep copy"
    project.mkdir()
    distribution_root.mkdir()
    editable_root.mkdir()
    neighbor_root.mkdir()
    source = editable_root / "editable_dependency.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    (neighbor_root / "editable_dependency.py").write_text("NEIGHBOR = 1\n", encoding="utf-8")
    direct_url = _editable_direct_url(editable_root.as_uri())
    direct_url_path = distribution_root / "direct_url.json"
    direct_url_path.write_text(direct_url, encoding="utf-8")
    distribution = _FakeDistribution(
        distribution_root,
        files=[Path(direct_url_path.name)],
        direct_url=direct_url,
    )
    # The editable root is deliberately NOT on sys.path: only the editable arm
    # of _installed_distribution_basis can observe drift inside it.
    monkeypatch.setattr(stats_module.sys, "path", [str(project), str(distribution_root)])
    monkeypatch.setattr(
        stats_module.importlib.metadata,
        "distributions",
        lambda: [cast("Distribution", distribution)],
    )
    before = _installed_distribution_basis(project, set())

    source.write_text("VALUE = 2\n", encoding="utf-8")
    after = _installed_distribution_basis(project, set())

    assert before.reuse_safe is True
    assert after.reuse_safe is True
    assert after.digest != before.digest

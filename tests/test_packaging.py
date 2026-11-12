"""Tests that the built wheel and sdist ship the plugin and nothing legacy."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tarfile
import zipfile

import pytest

ROOT = pathlib.Path(__file__).parent.parent

APPLICATION_MODULES = [
    "bluecore_graph_toolbox/api.py",
    "bluecore_graph_toolbox/deps.py",
    "bluecore_graph_toolbox/dashboard/routes.py",
    "bluecore_graph_toolbox/marc_bibframe_operations/routes.py",
    "bluecore_graph_toolbox/sparql/routes.py",
    "bluecore_graph_toolbox/ai_search/routes.py",
]

# What the removed standalone site and its XSLT conversion looked like.
LEGACY_SUFFIXES = (".xsl", "pyconfig.json", "mini-coi.js", ".whl")


@pytest.fixture(scope="module")
def dist(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is needed to build the distributions")
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(
        [uv, "build", "--quiet", "--out-dir", str(out)],
        cwd=ROOT,
        check=True,
    )
    return out


def _wheel_names(dist: pathlib.Path) -> list[str]:
    [wheel] = dist.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        return archive.namelist()


def _sdist_names(dist: pathlib.Path) -> list[str]:
    [sdist] = dist.glob("*.tar.gz")
    with tarfile.open(sdist) as archive:
        return archive.getnames()


def test_wheel_ships_every_application(dist: pathlib.Path) -> None:
    names = _wheel_names(dist)

    for module in APPLICATION_MODULES:
        assert module in names, module


@pytest.mark.parametrize("names", [_wheel_names, _sdist_names], ids=["wheel", "sdist"])
def test_distributions_ship_no_legacy_site_or_xslt(dist: pathlib.Path, names) -> None:
    legacy = [
        name
        for name in names(dist)
        if name.lower().endswith(LEGACY_SUFFIXES) or "saxon" in name.lower()
    ]

    assert legacy == []

"""Tests that installing the package is enough for Airflow to find the plugin."""

from __future__ import annotations

from importlib.metadata import entry_points, version

from airflow.plugins_manager import AirflowPlugin

from bluecore_graph_toolbox import __version__
from bluecore_graph_toolbox.plugin import GraphToolboxPlugin


def test_plugin_is_registered_as_an_airflow_entry_point() -> None:
    [entry_point] = entry_points(group="airflow.plugins", name="bluecore_graph_toolbox")

    assert entry_point.value == "bluecore_graph_toolbox.plugin:GraphToolboxPlugin"
    loaded = entry_point.load()
    assert loaded is GraphToolboxPlugin
    assert issubclass(loaded, AirflowPlugin)


def test_version_comes_from_the_installed_distribution() -> None:
    # __version__ looks itself up by distribution name, so renaming the
    # distribution without updating __init__.py falls back to 0.0.0+unknown.
    assert __version__ != "0.0.0+unknown"
    assert __version__ == version("bluecore-graph-toolbox")

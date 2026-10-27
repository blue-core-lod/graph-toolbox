"""Tests that installing the package is enough for Airflow to find the plugin."""

from __future__ import annotations

from importlib.metadata import entry_points

from airflow.plugins_manager import AirflowPlugin

from bluecore_graph_toolbox.plugin import GraphToolboxPlugin


def test_plugin_is_registered_as_an_airflow_entry_point() -> None:
    [entry_point] = entry_points(group="airflow.plugins", name="bluecore_graph_toolbox")

    assert entry_point.value == "bluecore_graph_toolbox.plugin:GraphToolboxPlugin"
    loaded = entry_point.load()
    assert loaded is GraphToolboxPlugin
    assert issubclass(loaded, AirflowPlugin)

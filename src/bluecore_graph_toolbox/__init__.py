"""Blue Core Graph Toolbox, packaged as an Airflow 3 plugin."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("blue-core-graph-toolbox")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

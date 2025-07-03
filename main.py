__version__ = "1.1.0"
import asyncio
import sys
import js
import pathlib
import tomllib

from pyodide.ffi import create_proxy

import helpers

import rdflib


FILE = pathlib.Path(".")

BIBFRAME = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
SINOPIA = rdflib.Namespace("http://sinopia.io/vocabulary/")

from helpers import bluecore_login
from sinopia_api import show_groups
from load_rdf import bibframe_sparql as bf_sparql_widget, build_graph, download_graph
from query_rdf import download_query_results, run_query

bf_sparql_widget("bf-sparql-query")

pyproject = FILE.parent / "pyproject.toml"

if pyproject.exists():
    with pyproject.open('rb') as fo: 
        project = tomllib.load(fo)
        version = project["project"]["version"]
else:
    version = __version__
helpers.set_versions(version)

splash_modal_close_btn = js.document.getElementById("splashModalCloseBtn")
splash_modal_close_btn.click()

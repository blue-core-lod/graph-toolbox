import asyncio
import sys

import pathlib
import tomllib


import rdflib

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


toolbox = FastAPI()
toolbox.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@toolbox.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    ) 

# FILE = pathlib.Path(".")

# SINOPIA = rdflib.Namespace("http://sinopia.io/vocabulary/")

# from bluecore_api import bluecore_login, save_bluecore, search_bluecore, set_environment
# from sinopia_api import show_groups
# from load_rdf import (
#     bibframe_sparql as bf_sparql_widget,
#     build_graph,
#     download_graph,
#     load_cbd_file,
# )
# from marc import bf2marc, marc2bf
# from query_rdf import download_query_results, run_query, run_summary_query
# from validation import validate

# bf_sparql_widget("bf-sparql-query")


# async def retrieve_version():
#     pyproject_request = await pyfetch("pyproject.toml")
#     pyproject = await pyproject_request.text()
#     project = tomllib.loads(pyproject)
#     version = project["project"]["version"]
#     return version


# version = await retrieve_version()

# helpers.set_versions(version)

# splash_modal_close_btn = js.document.getElementById("splashModalCloseBtn")
# splash_modal_close_btn.click()

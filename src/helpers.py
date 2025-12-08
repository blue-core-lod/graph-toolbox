import markdown
import rdflib
import tomllib

from js import document
from pyodide.http import pyfetch


BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")
BFLC = rdflib.Namespace("http://id.loc.gov/ontologies/bflc/")
MADS = rdflib.Namespace("http://www.loc.gov/mads/rdf/v1#")
SINOPIA = rdflib.Namespace("http://sinopia.io/vocabulary/")

# Define common BF RDF namespaces
NAMESPACES = [
    ("bf", BF),
    ("bflc", BFLC),
    ("mads", MADS),
    ("sinopia", SINOPIA),
]

def set_versions(version):
    version_element = document.getElementById("version")
    footer_version = document.getElementById("footer-version")
    version_element.innerHTML = version
    footer_version.innerHTML = version


async def retrieve_version():
    pyproject_request = await pyfetch("pyproject.toml")
    pyproject = await pyproject_request.text()
    project = tomllib.loads(pyproject)
    version = project["project"]["version"]
    set_versions(version)


async def render_markdown(element_id):
    element = document.getElementById(element_id)
    if element is None:
        return
    raw_mkdwn = element.innerText
    element.innerHTML = markdown.markdown(raw_mkdwn)


async def py_repl(event):
    py_repl_div = document.getElementById("py-repl")
    if "d-none" in py_repl_div.classList:
        py_repl_div.classList.remove("d-none")
    else:
        py_repl_div.classList.add("d-none")

import markdown
import rdflib

from js import document
    
BF = rdflib.Namespace("http://id.loc.gov/ontologies/bibframe/")

def set_versions(version):
    version_element = document.getElementById("version")
    footer_version = document.getElementById("footer-version")
    version_element.innerHTML = version
    footer_version.innerHTML = version


async def render_markdown(element_id):
    element = document.getElementById(element_id)
    if element is None:
        return
    raw_mkdwn = element.innerText
    element.innerHTML = markdown.markdown(raw_mkdwn)

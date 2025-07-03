import js
import markdown

from js import document, console


async def bluecore_login(event):
    console.log(f"Starting Blue Core Login")
   
    

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


from puepy import Application, Page, t
from puepy.router import Router
from components import GraphInfoToolbar

app = Application()
app.install_router(Router, link_mode=Router.LINK_MODE_HASH)


@app.page()
class BlueCoreToolboxPage(Page):
    def populate(self):
        t.h1("Graph Toolbox")
        t.graph_info_toolbar()

app.mount("#app")

from puepy import Application, Component, Page, t
from puepy.core import html
from puepy.router import Router


app = Application()
app.install_router(Router, link_mode=Router.LINK_MODE_HASH)


@app.page()
class BlueCoreToolboxPage(Page):

    def populate(self):
        t.h1("Graph Toolbox")

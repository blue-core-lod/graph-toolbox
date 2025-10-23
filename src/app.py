
from puepy import Application, Page, t
from puepy.router import Router

app = Application()
app.install_router(Router, link_mode=Router.LINK_MODE_HASH)


@app.page()
class BlueCoreToolboxPage(Page):
    def populate(self):
        t.navbar()
        t.graph_info_toolbar()
        with t.div(class_name="row"):
            with t.div(class_name="col-4"):
                t.graph_search_query_toolbar()
            with t.div(class_name="col-7"):
                t.graph_work_bench()
            with t.div(class_name="col-1"):
                t.graph_ops_toolbar()
        t.app_footer()

app.mount("#app")
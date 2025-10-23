from puepy import Application, Page, t
from puepy.router import Router
from components import (
    GraphInfoToolbar,
    GraphOpsToolbar,
    GraphSearchQueryToolbar,
    GraphWorkBench,
    Navbar,
    AppFooter,
)
from modals import (
    AiAssistanceModal,
    BulkModal,
    CbdModal,
    LoadModal,
    MarcExportModal,
    MarcImportModal,
    SparqlModal,
    UrlsModal,
    LoginModal,
)

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

        # Modals
        t.ai_assistance_modal()
        t.bulk_modal()
        t.cbd_modal()
        t.load_modal()
        t.marc_export_modal()
        t.marc_import_modal()
        t.sparql_modal()
        t.urls_modal()
        t.login_modal()


app.mount("#app")

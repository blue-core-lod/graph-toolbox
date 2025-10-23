from puepy import Component, t


@t.component()
class AiAssistanceModal(Component):
    """
    AI Assistance modal component.

    Provides a large modal dialog for AI assistance interactions.
    """

    def populate(self):
        with t.div(classes=["modal", "fade"], tabindex="-1", id="ai-assistance-modal"):
            with t.div(classes=["modal-dialog", "modal-lg"]):
                with t.div(classes=["modal-content"]):
                    # Header
                    with t.div(classes=["modal-header"]):
                        t.h5("AI Assistance", classes=["modal-title"])
                        t.button(
                            type="button",
                            classes=["btn-close"],
                            data_bs_dismiss="modal",
                            aria_label="Close",
                        )

                    # Body (empty for now, can be populated dynamically)
                    t.div(classes=["modal-body"])

                    # Footer
                    with t.div(classes=["modal-footer"]):
                        t.button(
                            "Close",
                            type="button",
                            classes=["btn", "btn-secondary"],
                            data_bs_dismiss="modal",
                        )


@t.component()
class BulkModal(Component):
    """
    Bulk updates modal component.

    Provides instructions for performing bulk updates on resources.
    """

    def populate(self):
        with t.div(classes=["modal", "fade"], tabindex="-1", id="bulk-modal"):
            with t.div(classes=["modal-dialog"]):
                with t.div(classes=["modal-content"]):
                    # Header
                    with t.div(classes=["modal-header"]):
                        t.h5("Bulk Updates", classes=["modal-title"])
                        t.button(
                            type="button",
                            classes=["btn-close"],
                            data_bs_dismiss="modal",
                            aria_label="Close",
                        )

                    # Body
                    with t.div(classes=["modal-body"]):
                        t.p(
                            "To perform bulk updates, follow these steps:",
                            classes=["text-secondary"],
                        )
                        with t.ol():
                            with t.li():
                                t(
                                    "Load the graphs for those resources you want to update (limited by the available memory in your web-browser)"
                                )

                            with t.li():
                                t("Construct an ")
                                t.a(
                                    "Update",
                                    href="https://www.w3.org/TR/sparql11-update/",
                                )
                                t(" SPARQL query to apply to the resources.")

                            with t.li():
                                t(
                                    "Run Query and confirm that the changes reflect what you want updated."
                                )

                            with t.li():
                                t("Save the resulting changed graph(s) to Blue Core")

                    # Footer
                    with t.div(classes=["modal-footer"]):
                        t.button(
                            "Close",
                            type="button",
                            classes=["btn", "btn-secondary"],
                            data_bs_dismiss="modal",
                        )


@t.component()
class CbdModal(Component):
    """
    Constrained Bound Descriptions (CBD) modal component.

    Provides interface for loading CBD files and URLs.
    """

    def populate(self):
        with t.div(classes=["modal", "fade"], tabindex="-1", id="cbd-modal"):
            with t.div(classes=["modal-dialog"]):
                with t.div(classes=["modal-content"]):
                    # Header
                    with t.div(classes=["modal-header"]):
                        t.h5(
                            "Constrained Bound Descriptions (CBD)",
                            classes=["modal-title"],
                        )
                        t.button(
                            type="button",
                            classes=["btn-close"],
                            data_bs_dismiss="modal",
                            aria_label="Close",
                        )

                    # Body
                    with t.div(classes=["modal-body"]):
                        # Upload file section
                        t.label("Upload file", for_="cbd-file", classes=["form-label"])
                        with t.div(classes=["input-group"]):
                            t.input(
                                classes=["form-control"], type="file", id="cbd-file"
                            )
                            t.button(
                                "Load",
                                classes=["btn", "btn-outline-secondary"],
                                type="button",
                                id="cbd-file-btn",
                                on_click=self.load_cbd_file,
                            )

                        # CBD URL section
                        t.label("CBD URL", for_="cbd-url", classes=["form-label"])
                        with t.div(classes=["input-group"]):
                            t.input(
                                type="text",
                                id="cbd-url",
                                classes=["form-control"],
                                placeholder="Load CBD URL",
                                aria_label="Load CBD URL",
                                aria_describedby="cbd-url-btn",
                            )
                            t.button(
                                "Load",
                                classes=["btn", "btn-outline-secondary"],
                                type="button",
                                id="cbd-url-btn",
                            )

                        # Upload zip file section
                        t.label(
                            "Upload Multiple CBD records in a Zip File",
                            for_="cbd-zip-file",
                            classes=["form-label"],
                        )
                        with t.div(classes=["input-group"]):
                            t.input(
                                classes=["form-control"], type="file", id="cbd-zip-file"
                            )
                            t.button(
                                "Load",
                                classes=["btn", "btn-outline-secondary"],
                                type="button",
                                id="cbd-zip-file-btn",
                                on_click=self.load_cbd_zip_file,
                            )

                    # Footer
                    with t.div(classes=["modal-footer"]):
                        t.button(
                            "Close",
                            type="button",
                            classes=["btn", "btn-secondary"],
                            data_bs_dismiss="modal",
                            id="cbd-modal-close-btn",
                        )

    def load_cbd_file(self, event):
        """Handle CBD file upload."""
        # TODO: Implement CBD file loading
        pass

    def load_cbd_zip_file(self, event):
        """Handle CBD zip file upload."""
        # TODO: Implement CBD zip file loading
        pass


@t.component()
class LoadModal(Component):
    """
    Loading/splash modal component.

    Displays during initialization with a loading spinner.
    """

    def populate(self):
        with t.div(classes=["modal", "fade"], tabindex="-1", id="splashModal"):
            with t.div(classes=["modal-dialog", "modal-fullscreen-sm-down"]):
                with t.div(classes=["modal-content"]):
                    # Header
                    with t.div(classes=["modal-header"]):
                        t.h5("Graph Toolbox Initialization", classes=["modal-title"])
                        t.button(
                            type="button",
                            id="splashModalCloseBtn",
                            classes=["btn-close"],
                            data_bs_dismiss="modal",
                            aria_label="Close",
                        )

                    # Body
                    with t.div(classes=["modal-body"]):
                        t("Loading...")
                        with t.div(
                            classes=["spinner-border", "text-secondary"], role="status"
                        ):
                            t.span("Loading...", classes=["visually-hidden"])


@t.component()
class MarcExportModal(Component):
    """
    MARC export modal component.

    Provides interface for exporting BIBFRAME to MARC21 or MARC XML.
    """

    def populate(self):
        with t.div(classes=["modal", "fade"], tabindex="-1", id="marc21-export-modal"):
            with t.div(classes=["modal-dialog"]):
                with t.div(classes=["modal-content"]):
                    # Header
                    with t.div(classes=["modal-header"]):
                        with t.h5(classes=["modal-title"]):
                            t.img(
                                src="static/img/marc21h2.gif",
                                width="32px",
                                height="32px",
                            )
                            t(" MARC Export")
                        t.button(
                            type="button",
                            classes=["btn-close"],
                            data_bs_dismiss="modal",
                            aria_label="Close",
                        )

                    # Body
                    with t.div(classes=["modal-body"]):
                        with t.p():
                            t(
                                "Export BIBFRAME Works and Instances to MARC21 or MARC XML using "
                            )
                            t.a(
                                "bibframe2marc",
                                href="https://github.com/lcnetdev/bibframe2marc",
                            )
                            t(".")

                        with t.div(classes=["dropdown"]):
                            t.button(
                                "Download MARC",
                                classes=["btn", "btn-secondary", "dropdown-toggle"],
                                type="button",
                                data_bs_toggle="dropdown",
                                id="marc-download",
                                aria_expanded="false",
                            )
                            with t.ul(classes=["dropdown-menu"]):
                                with t.li():
                                    t.a(
                                        "MARC21",
                                        classes=["dropdown-item"],
                                        href="#",
                                        on_click=lambda e: self.bf2marc(e, "marc21"),
                                    )
                                with t.li():
                                    t.a(
                                        "MARC XML",
                                        classes=["dropdown-item"],
                                        href="#",
                                        on_click=lambda e: self.bf2marc(e, "marcXML"),
                                    )

                    # Footer
                    with t.div(classes=["modal-footer"]):
                        t.button(
                            "Close",
                            type="button",
                            classes=["btn", "btn-secondary"],
                            data_bs_dismiss="modal",
                        )

    def bf2marc(self, event, marc_format):
        """Handle BIBFRAME to MARC conversion."""
        # TODO: Implement BIBFRAME to MARC conversion
        pass


@t.component()
class MarcImportModal(Component):
    """
    MARC import modal component.

    Provides interface for importing MARC21 or MARC XML files and converting to BIBFRAME.
    """

    def populate(self):
        with t.div(classes=["modal", "fade"], tabindex="-1", id="marc21-import-modal"):
            with t.div(classes=["modal-dialog"]):
                with t.div(classes=["modal-content"]):
                    # Header
                    with t.div(classes=["modal-header"]):
                        with t.h5(classes=["modal-title"]):
                            t.img(
                                src="static/img/marc21h2.gif",
                                width="32px",
                                height="32px",
                            )
                            t(" MARC Import")
                        t.button(
                            type="button",
                            classes=["btn-close"],
                            data_bs_dismiss="modal",
                            aria_label="Close",
                        )

                    # Body
                    with t.div(classes=["modal-body"]):
                        with t.p():
                            t(
                                "Upload a MARC21 or MARC XML file and convert to BIBFRAME using "
                            )
                            t.a(
                                "marc2bibframe2",
                                href="https://github.com/lcnetdev/marc2bibframe2",
                            )
                            t(".")

                        t.label(
                            "Upload MARC file", for_="marc-file", classes=["form-label"]
                        )
                        with t.div(classes=["input-group"]):
                            t.input(
                                classes=["form-control"], type="file", id="marc-file"
                            )
                            t.button(
                                "Convert",
                                classes=["btn", "btn-outline-secondary"],
                                type="button",
                                id="marc-file-btn",
                                on_click=self.marc2bf,
                            )

                    # Footer
                    with t.div(classes=["modal-footer"]):
                        t.button(
                            "Close",
                            type="button",
                            classes=["btn", "btn-secondary"],
                            data_bs_dismiss="modal",
                        )

    def marc2bf(self, event):
        """Handle MARC to BIBFRAME conversion."""
        # TODO: Implement MARC to BIBFRAME conversion
        pass


@t.component()
class SparqlModal(Component):
    """
    SPARQL query modal component.

    Provides a large modal dialog for SPARQL query editing.
    """

    def populate(self):
        with t.div(classes=["modal", "fade"], tabindex="-1", id="sparql-modal"):
            with t.div(classes=["modal-dialog", "modal-lg"]):
                with t.div(classes=["modal-content"]):
                    # Header
                    with t.div(classes=["modal-header"]):
                        t.h5("SPARQL Query", classes=["modal-title"])
                        t.button(
                            type="button",
                            classes=["btn-close"],
                            data_bs_dismiss="modal",
                            aria_label="Close",
                        )

                    # Body (empty for now, can be populated dynamically)
                    t.div(classes=["modal-body"])

                    # Footer
                    with t.div(classes=["modal-footer"]):
                        t.button(
                            "Close",
                            type="button",
                            classes=["btn", "btn-secondary"],
                            data_bs_dismiss="modal",
                        )


@t.component()
class UrlsModal(Component):
    """
    Individual URLs modal component.

    Provides interface for adding individual resource URLs to the graph.
    """

    def populate(self):
        with t.div(classes=["modal", "fade"], tabindex="-1", id="urls-modal"):
            with t.div(classes=["modal-dialog"]):
                with t.div(classes=["modal-content"]):
                    # Header
                    with t.div(classes=["modal-header"]):
                        with t.h5(classes=["modal-title"]):
                            t.i(classes=["bi", "bi-window-stack"])
                            t(" Individual URLs")
                        t.button(
                            type="button",
                            classes=["btn-close"],
                            data_bs_dismiss="modal",
                            aria_label="Close",
                        )

                    # Body
                    with t.div(classes=["modal-body"]):
                        t.p(
                            "Add URLs of Individual Resources to add to Graph (separate by commas)",
                            classes=["form-text"],
                        )
                        with t.div():
                            t.textarea(
                                classes=["form-control"],
                                cols=25,
                                rows=3,
                                id="resource-urls",
                            )

                    # Footer
                    with t.div(classes=["modal-footer"]):
                        with t.button(
                            classes=["btn", "btn-primary"], on_click=self.build_graph
                        ):
                            t.i(
                                classes=["spinner-border", "d-none"],
                                id="graph-loading-status",
                            )
                            t(" Build Graph")

                        t.button(
                            "Close",
                            type="button",
                            classes=["btn", "btn-secondary"],
                            data_bs_dismiss="modal",
                        )

    def build_graph(self, event):
        """Handle building graph from URLs."""
        # TODO: Implement graph building from URLs
        pass


@t.component()
class LoginModal(Component):
    """
    Login modal component.

    Provides Keycloak login interface for Blue Core authentication.
    """

    def populate(self):
        with t.div(classes=["modal", "fade"], tabindex="-1", id="loginModal"):
            with t.div(classes=["modal-dialog", "modal-fullscreen-sm-down"]):
                with t.div(classes=["modal-content"]):
                    # Header
                    with t.div(classes=["modal-header"]):
                        t.h5("Blue Core Keycloak Login", classes=["modal-title"])
                        t.button(
                            type="button",
                            id="loginModalhModalCloseBtn",
                            classes=["btn-close"],
                            data_bs_dismiss="modal",
                            aria_label="Close",
                        )

                    # Body
                    with t.div(classes=["modal-body"]):
                        # Username field
                        with t.div(classes=["mb-3"]):
                            t.label(
                                "Username",
                                for_="keycloak_username",
                                classes=["form-label"],
                            )
                            t.input(
                                type="text",
                                classes=["form-control"],
                                id="keycloak_username",
                                placeholder="Enter Username",
                            )

                        # Password field
                        with t.div(classes=["mb-3"]):
                            t.label(
                                "Password",
                                for_="keycloak_password",
                                classes=["form-label"],
                            )
                            t.input(
                                type="password",
                                classes=["form-control"],
                                id="keycloak_password",
                                placeholder="Enter password",
                            )

                    # Footer
                    with t.div(classes=["modal-footer"]):
                        t.button(
                            "Close",
                            type="button",
                            classes=["btn", "btn-secondary"],
                            data_bs_dismiss="modal",
                        )
                        t.button(
                            "Login",
                            type="button",
                            classes=["btn", "btn-primary"],
                            on_click=self.bluecore_login,
                        )

    def bluecore_login(self, event):
        """Handle Blue Core login."""
        # TODO: Implement Blue Core Keycloak login
        pass

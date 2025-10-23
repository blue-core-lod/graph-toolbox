from puepy import Component, t
from js import console

console.log("components.py module loaded!")

@t.component()
class GraphInfoToolbar(Component):
    """
    Graph summary toolbar component displaying RDF graph statistics and actions.

    Shows counts for:
    - Total triples (calculated from BF_GRAPH in app state)
    - Subjects, Predicates, Objects (calculated from BF_GRAPH in app state)
    - BF Works and BF Instances

    Provides actions for:
    - Running summary queries
    - Bulk updates (modal)
    - Saving entities to Blue Core
    """

    # Redraw when the graph state changes
    redraw_on_app_state_changes = ["bf_graph", "bf_works_count", "bf_instances_count"]

    def __init__(self, *args, **kwargs):
        console.log("GraphInfoToolbar.__init__ called")
        super().__init__(*args, **kwargs)
        console.log("GraphInfoToolbar.__init__ completed")

    @property
    def bf_graph(self):
        """Get the BF_GRAPH from application state."""
        return self.application.state.get("bf_graph")

    @property
    def total_triples(self):
        """Calculate total triples from the graph."""
        return len(self.bf_graph) if self.bf_graph else 0

    @property
    def subjects_count(self):
        """Calculate unique subjects from the graph."""
        return len(set(self.bf_graph.subjects())) if self.bf_graph else 0

    @property
    def predicates_count(self):
        return len(set(self.bf_graph.predicates())) if self.bf_graph else 0

    @property
    def objects_count(self):
        """Calculate unique objects from the graph."""
        return len(set(self.bf_graph.objects())) if self.bf_graph else 0

    @property
    def bf_works_count(self):
        """Get BF Works count from application state."""
        if not self.bf_graph:
            return 0
        works_result = self.bf_graph.query(
        """
        PREFIX bf: <http://id.loc.gov/ontologies/bibframe/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT (count(DISTINCT ?s) as ?workCount)
        WHERE { ?s rdf:type bf:Work . }
        """
        )
        return works_result.bindings[0]["workCount"].value if works_result.bindings else 0

    @property
    def bf_instances_count(self):
        """Get BF Instances count from application state."""
        if not self.bf_graph:
            return 0
        instances_result = self.bf_graph.query(
        """
        PREFIX bf: <http://id.loc.gov/ontologies/bibframe/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT (count(DISTINCT ?s) as ?instanceCount)
        WHERE { ?s rdf:type bf:Instance . }
        """
        )
        return instances_result.bindings[0]["instanceCount"].value if instances_result.bindings else 0

    def populate(self):
        console.log("GraphInfoToolbar.populate() called!")
        with t.div(classes=["container"]):
            with t.div(classes=["row", "bg-secondary-subtle", "rounded-2", "mb-2"]):
                # Title section
                with t.div(classes=["col-2", "d-flex", "flex-grow-1", "justify-content-center", "align-items-center"]):
                    t.h5("Graph Summary")

                # Summary buttons section
                with t.div(classes=["col-6", "d-flex", "flex-grow-1", "justify-content-center", "align-items-center"]):
                    with t.div(class_name="btn-group", role="group", aria_label="Graph Summary Button Group"):
                        # Total Triples button
                        with t.button(
                            type="button",
                            classes=["btn", "btn-success"],
                            on_click=lambda event: self.on_run_summary_query(event, "all")
                        ):
                            t("Total Triples")
                            t(" ")
                            t.span(str(self.total_triples), classes=["badge", "text-bg-secondary"])

                        # Subjects button
                        with t.button(
                            type="button",
                            classes=["btn", "btn-info"],
                            on_click=lambda event: self.on_run_summary_query(event, "subject")
                        ):
                            t("Subjects")
                            t(" ")
                            t.span(str(self.subjects_count), classes=["badge", "text-bg-secondary"])

                        # Predicates button
                        with t.button(
                            type="button",
                            classes=["btn", "btn-primary"],
                            on_click=lambda event: self.on_run_summary_query(event, "predicate")
                        ):
                            t("Predicates")
                            t(" ")
                            t.span(str(self.predicates_count), classes=["badge", "text-bg-secondary"])

                        # Objects button
                        with t.button(
                            type="button",
                            classes=["btn", "btn-info"],
                            on_click=lambda event: self.on_run_summary_query(event, "object")
                        ):
                            t("Objects")
                            t(" ")
                            t.span(str(self.objects_count), classes=["badge", "text-bg-secondary"])

                # BF Works/Instances counts section
                with t.div(classes=["col-2"]):
                    with t.ul():
                        with t.li():
                            t("BF Works: ")
                            t.span(str(self.bf_works_count), classes=["badge", "text-bg-secondary"])
                        with t.li():
                            t("BF Instances: ")
                            t.span(str(self.bf_instances_count), classes=["badge", "text-bg-secondary"])

                # Action buttons section
                with t.div(classes=["col-2", "d-flex", "flex-grow-1", "justify-content-center", "align-items-center"]):
                    with t.div(classes=["btn-group"], role="group"):
                        # Bulk Updates button
                        with t.button(
                            type="button",
                            classes=["btn", "btn-warning"],
                            data_bs_toggle="modal",
                            data_bs_target="#bulk-modal"
                        ):
                            t.i(classes=["bi", "bi-files"], data_bs_toggle="tooltip", data_bs_title="Bulk Updates")

                        # Save to Blue Core button
                        with t.button(
                            type="button",
                            classes=["btn", "btn-warning"],
                            on_click=self.on_save_bluecore,
                            data_bs_toggle="tooltip",
                            data_bs_title="Save Entities to Blue Core"
                        ):
                            t.i(classes=["bi", "bi-floppy"])

    def on_run_summary_query(self, event, query_type):
        """
        Handle summary query button clicks.

        Args:
            event: The click event
            query_type: Type of query ('all', 'subject', 'predicate', 'object')
        """
        # TODO: Implement query logic
        # This should query the RDF graph and update the corresponding count
        console.log(f"Running summary query: {query_type}")


    def on_save_bluecore(self, event):
        """
        Handle save to Blue Core button click.

        Args:
            event: The click event
        """
        # TODO: Implement save to Blue Core logic
        console.log("Saving entities to Blue Core")

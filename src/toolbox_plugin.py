from airflow.plugins_manager import AirflowPlugin

toolbox_view_with_metadata = {
    "name": "Graph Toolbox",
    "destination": "nav",
    "url_route": "graph_toolbox_view",
    "category": "toolbox",
}


class GraphToolboxPlugin(AirflowPlugin):
    name = "graph_toolbox"
    macros = []
    external_views = [toolbox_view_with_metadata]

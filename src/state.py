import rdflib

NAMESPACES = [
    ("bf", "http://id.loc.gov/ontologies/bibframe/"),
    ("bflc", "http://id.loc.gov/ontologies/bflc/"),
    ("sinopia", "http://sinopia.io/vocabulary/"),
]

BF_GRAPH = rdflib.Graph()

RESULTS_DF = None

for ns in NAMESPACES:
    BF_GRAPH.namespace_manager.bind(ns[0], ns[1])

BLUECORE_ENV = None
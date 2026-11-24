"""Write the Toolbox API's OpenAPI document to docs/openapi.json.

The plugin doesn't serve its OpenAPI document, so this file is how the UI
(#40) and anyone else integrating learn the routes and shapes. Run it after
changing a route or model, and commit the result:

    uv run python scripts/openapi.py
"""

from __future__ import annotations

import json
import pathlib

from bluecore_graph_toolbox import __version__
from bluecore_graph_toolbox.plugin import app

OUTPUT = pathlib.Path(__file__).parent.parent / "docs" / "openapi.json"


def main() -> None:
    document = app.openapi()
    document["info"]["version"] = __version__
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()

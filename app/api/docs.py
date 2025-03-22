"""
Endpoint to serve the ReadTheDocs docs as static files.
"""

import os
import logging
from microdot.asgi import Microdot, redirect, send_file

from app.config import (
    APP_DOCS_DIR,
    APP_DOCS_PATH,
)

logger = logging.getLogger(__name__)
app = Microdot()


@app.get("/")
async def appDocsIndex(_):
    """
    App docs root - we just redirect to the ``index.html`` relative to theis
    dir.
    """
    return redirect("index.html")


@app.get("/<path:path>")
async def appDocs(_, path):
    """
    Servers static app docs...

    ToDo: Fix me....
    """
    if ".." in path:
        # directory traversal is not allowed
        return "Not found", 404
    f_path = f"{APP_DOCS_DIR}/{path}"
    if not os.path.exists(f_path) or os.path.isdir(f_path):
        return "Not found", 404
    return send_file(f_path, max_age=86400)

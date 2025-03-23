"""
Main application entry point.
"""

import os
import logging

from microdot.asgi import Microdot, redirect, send_file
from app.api.soc import app as soc_app
from app.api.docs import app as docs_app

from .config import (
    APP_DOCS_PATH,
    MOUNT_APP_DOCS,
    STATIC_DIR,
)

logger = logging.getLogger(__name__)

app = Microdot()
# The SoC endpoints are mounted on the /api path prefix
app.mount(soc_app, url_prefix="/api")

# Mount the APP API docs?
if MOUNT_APP_DOCS:
    logging.info("Mounting app docs on %s", APP_DOCS_PATH)
    app.mount(docs_app, url_prefix=f"/{APP_DOCS_PATH}")


# app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


@app.get("/")
async def index(_):
    """
    App root - we just redirect to the ``index.html`` relative to this path.
    """
    return redirect("index.html")


@app.get("/<path:path>")
async def static(_, path):
    """
    Servers static files...

    ToDo: Fix me....
    """
    if ".." in path:
        # directory traversal is not allowed
        return "Not found", 404
    f_path = f"{STATIC_DIR}/{path}"
    if not os.path.exists(f_path) or os.path.isdir(f_path):
        return "Not found", 404
    return send_file(f_path, max_age=86400)


logging.debug("App starting...")

# We will normally run under behind uvicorn, but if you need to run the local
# Microdot webserver, uncomment this.
# app.run(port=8000, debug=True)

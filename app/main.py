"""
Main application entry point.
"""

import os
import logging

# We set the logger up as early as possible. If there is an APP_LOGLEVEL
# environment variable, we expect it to be "DEBUG", "INFO", etc. If this is a
# valid log level we will set to that level, else fall back to INFO
# pylint: disable=wrong-import-position
LOGLEVEL = os.getenv("APP_LOGLEVEL") or "INFO"
logging.basicConfig(level=getattr(logging, LOGLEVEL, logging.INFO))
# pylint: enable=wrong-import-position

from microdot.asgi import Microdot, send_file, redirect

from app import data

from .config import (
    VERSION,
    APP_DOCS_DIR,
    APP_DOCS_PATH,
    MOUNT_APP_DOCS,
    FAVICON_PATH,
    STATIC_PATH,
)

logger = logging.getLogger(__name__)

app = Microdot()

# Mount the APP API docs?
if MOUNT_APP_DOCS:

    @app.get(f"/{APP_DOCS_PATH}/")
    async def appDocsIndex(_):
        """
        App docs root - we just redirect to the ``index.html`` relative to theis
        dir.
        """
        return redirect("index.html")

    @app.get(f"/{APP_DOCS_PATH}/<path:path>")
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
        return send_file(f"{APP_DOCS_DIR}/{path}", max_age=86400)


# app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


@app.get("/")
async def index(_):
    """
    Handler for the root path.
    """
    return "Hello, world!"


@app.get("/battery_ids")
async def batteryIDs(_):
    """
    Returns a list of all knows Battery IDs.
    """
    return list(data.getAllBatIDs())


@app.get("/soc_events/<string:bat_id>")
async def socEvents(_, bat_id):
    """
    Returns a list of SoC Events for a given battery ID.
    """
    return list(data.getSoCEvents(bat_id))


@app.get("/soc_measures/<string:uid>")
async def socMeasures(_, uid):
    """
    Returns a list of all SoC Measure events for a given SoC UID
    """
    return list(data.getSoCMeasures(uid))


@app.get("/soc_avg/<string:uid>")
async def socqAvg(request, uid):
    """
    Returns the average SoC by UID....

    ToDo: Fix the docs....
    """

    print(f"Args: {request.args}, {'single' in request.args}")
    if "single" in request.args:
        return {"mAh_avg": data.getSoCAvg(uid, single=True)}

    return list(data.getSoCAvg(uid))


logging.debug("App starting...")

# We will normally run under behind uvicorn, but if you need to run the local
# Microdot webserver, uncomment this.
# app.run(port=8000, debug=True)

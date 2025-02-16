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
from app.api.soc import app as soc_app
from app.api.docs import app as docs_app

from .config import (
    APP_DOCS_DIR,
    APP_DOCS_PATH,
    MOUNT_APP_DOCS,
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
    Handler for the root path.
    """
    return "Hello, world!"


logging.debug("App starting...")

# We will normally run under behind uvicorn, but if you need to run the local
# Microdot webserver, uncomment this.
# app.run(port=8000, debug=True)

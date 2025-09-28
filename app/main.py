"""
Main application entry point.

Attributes:

    app: The main Microdot_ application instance. Sub applications will be
        imported from other modules and mounted onto this app and their own
        base URL paths.
    logger: The module level logger

.. _Microdot: https://microdot.readthedocs.io/en/latest/index.html
"""

import os
import logging

from microdot.asgi import Microdot, Response, Request, send_file
from microdot.utemplate import Template

from .events import (
    events,
    BASE_URL as BASE_EVENTS,
)
from .events_summary import (
    events_sum,
    BASE_URL as BASE_EVENTS_SUM,
)
from .batteries import (
    bat,
    BASE_URL as BASE_BAT,
)
from .bcm_state import (
    bcm_state,
    BASE_URL as BASE_BCM_STATE,
)
from .calibration import (
    calib,
    BASE_URL as BASE_CALIB,
)
from .bat_packs import (
    pack,
    BASE_URL as BASE_PACK,
)
from .logs import (
    logs,
    BASE_URL as BASE_LOGS,
)

from .config import (
    APP_DOCS_PATH,
    MOUNT_APP_DOCS,
    STATIC_DIR,
    TMPL_DIR,
    BAT_IMG_MAX_SZ,
)

from .index import (
    renderIndex,
)


# We need to allow for battery images to be uploaded larger than the default
# Microdot content size, so we set the default here.
# See also the batImageSet handler.
Request.max_content_length = int(BAT_IMG_MAX_SZ * 5.5)

logger = logging.getLogger(__name__)

# Set the base for our templates
Template.initialize(TMPL_DIR)

# Ensure we return text/html as the default application type
Response.default_content_type = "text/html"

# Set up the main and all sub apps
app = Microdot()
app.mount(events, url_prefix=BASE_EVENTS)
app.mount(events_sum, url_prefix=BASE_EVENTS_SUM)
app.mount(bat, url_prefix=BASE_BAT)
app.mount(bcm_state, url_prefix=BASE_BCM_STATE)
app.mount(calib, url_prefix=BASE_CALIB)
app.mount(pack, url_prefix=BASE_PACK)
app.mount(logs, url_prefix=BASE_LOGS)

# Mount the APP API docs?
if MOUNT_APP_DOCS:
    from .docs_server import app as docs_app

    logging.info("Mounting app docs on %s", APP_DOCS_PATH)
    app.mount(docs_app, url_prefix=f"/{APP_DOCS_PATH}")


# app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


@app.get("/")
async def index(_):
    """
    App root.

    We simply render the index.html template
    """
    return renderIndex()


@app.get("/<path:path>")
async def static(_, path):
    """
    Servers static files...

    ToDo: Fix me....
    """
    if ".." in path:
        # directory traversal is not allowed
        return "Don't be naughty now :-)", 404
    f_path = f"{STATIC_DIR}/{path}"
    if not os.path.exists(f_path) or os.path.isdir(f_path):
        return "Not found", 404

    # Try to set the content type for specific files, and leave send_file to
    # figure it out otherwise
    content_type = None
    if path.endswith(".svg"):
        content_type = "image/svg+xml"

    return send_file(f_path, content_type=content_type, max_age=86400)


logging.debug("App starting...")

# We will normally run under behind uvicorn, but if you need to run the local
# Microdot webserver, uncomment this.
# app.run(port=8000, debug=True)

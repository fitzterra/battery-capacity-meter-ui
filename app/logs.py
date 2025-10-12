"""
Page handlers for all things related to log handling in the info available in the
`Log` and model.

Attributes:
    calib: Microdot_ sub app to handle all events related endpoints. Will be
        mounted on the ``/calibration`` URL prefix
    logger: Local module logger.

.. _Microdot: https://microdot.readthedocs.io/en/latest/index.html
"""

import logging
import re
from datetime import datetime

from microdot.asgi import Microdot, Response, redirect
from microdot.utemplate import Template
from app.models.data import (
    getLogs,
    delLogs,
)

from .index import (
    renderIndex,
    flashMessage,
)

# Our local logger
logger = logging.getLogger(__name__)

# The base URL for this sub app. This should be without the trailing /
BASE_URL = "/logs"

# Creates the events handler sub app.
logs = Microdot()


@logs.get("/")
async def viewLogs(req):
    """
    List available logs...
    """

    page = int(req.args.get("page", 1))
    res = getLogs(page)

    content = Template("logs.html").render(**res)

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@logs.route("/cleanup", methods=["POST"])
def deleteLogs(req):
    """
    Handles deleting all log entries before a given date.

    Expects a "before_date" post variable as a string in the format::

        yyyy-mm-dd hh:mm:ss

    """
    logging.info("Requesting to delete logs...")
    # If we are not called from and HTMX request, we redirect to the main logs
    # view page
    if req.headers.get("Hx-Request", "false") == "false":
        logging.info("  Not an HTMX request. Redirecting to /logs/ ..")
        return redirect(f"{BASE_URL}/")

    before_date = req.form.get("before_date")
    # Check if the format matches the expected timestamp pattern
    ts_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
    if not re.match(ts_pattern, before_date):
        return flashMessage(f"Invalid timestamp format: {before_date}", "error")

    # Convert the string to a datetime object if valid
    try:
        before_date = datetime.strptime(before_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return flashMessage(f"Invalid timestamp value: {before_date}", "error")

    logging.info("  Logs before %s to deleted", before_date)

    res = delLogs(before_date)

    if not res["success"]:
        return flashMessage(res["msg"], "error")

    logging.info("  Logs delete result: %s", res)
    # Redirect to '/logs/'
    # Because the request came from HTMX, we need to handle the redirect
    # differently, or else the redirect URL will not be followed as a new page
    # request
    response = Response(status_code=302)
    response.headers["HX-Redirect"] = f"{BASE_URL}/"
    return response

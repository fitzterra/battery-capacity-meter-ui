"""
Page handlers for all things related to calibration info available in the
`BatCapHistory` and related models.

Attributes:
    calib: Microdot_ sub app to handle all events related endpoints. Will be
        mounted on the ``/calibration`` URL prefix

.. _Microdot: https://microdot.readthedocs.io/en/latest/index.html
"""

from microdot.asgi import Microdot
from microdot.utemplate import Template
from app.models.data import (
    bcCalibration,
    needsReTesting,
)


from .index import (
    renderIndex,
)

# The base URL for this sub app. This should be without the trailing /
BASE_URL = "/calibration"

# Creates the events handler sub app.
calib = Microdot()


@calib.get("/")
async def calibration(req):
    """
    View to display the BC calibration details.
    """
    res = bcCalibration()

    content = Template("bc_calibration.html").render(res)

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@calib.get("/needs_retest/")
async def retest(req):
    """
    Returns a list of any batteries that needs retesting if they have not been
    tested again after the latest BC calibrations.
    """
    # Get a list of batteries that needs re testing
    to_test = needsReTesting()

    content = Template("retest_after_calib.html").render(to_test)

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)

"""
Page handlers to generate the current BCM state for all BCs.

Attributes:
    calib: Microdot_ sub app to handle all events related endpoints. Will be
        mounted on the ``/calibration`` URL prefix

.. _Microdot: https://microdot.readthedocs.io/en/latest/index.html
"""

from microdot.asgi import Microdot
from microdot.utemplate import Template
from app.models.data.bcm_state import getState


from .index import (
    renderIndex,
)

# The base URL for this sub app. This should be without the trailing /
BASE_URL = "/bcm_state"

# Creates the events handler sub app.
bcm_state = Microdot()


@bcm_state.get("/")
async def state(req):
    """
    View to display the BCM state.
    """
    res = getState()

    content = Template("bcm_state.html").render(res)

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)

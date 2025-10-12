"""
Page handler for showing a summary of events for a given SoC event ID.

Since there are a huge amount of events per SoC cycle, being able to see just
those events at the start, end and all transitions in-between is helpful to
gain further insights.

Currently, accessing these pages can only be done from other pages where a SoC
UID is display and is not accessible directly from the menu.

There is only a root URL and the ``soc_uid`` must be passed in as query
parameter.
"""

from microdot.asgi import Microdot
from microdot.utemplate import Template
from app.models.data import getSummary


from .index import (
    renderIndex,
    errorResponse,
)

# The base URL for this sub app. This should be without the trailing /
BASE_URL = "/event_summary"

# Creates the events handler sub app.
events_sum = Microdot()


@events_sum.get("/")
async def showSummary(req):
    """
    Generates a summary view of `SoCEvent` entries for a given ``soc_uid``.

    The summary will show the first and last few entries, and a few entries
    around each transition between charge and discharge.

    The ``soc_uid`` is expected in a query parameter called ``soc_uid``.
    The number of events around transitions and start and end can be set with
    an ``event_count`` query parameter, but defaults to 5 if not supplied.

    Args:
        req: The ``microdot.request`` instance.

    Returns:
        The rendered HTML
    """
    # Get the soc_uid
    soc_uid = req.args.get("soc_uid")
    # Optionally events count, making sure it's and integer
    event_count = int(req.args.get("event_count", 5))

    # Get all events
    evts = getSummary(soc_uid=soc_uid, event_count=event_count)
    content = Template("event_summary.html").render(
        events=evts,
        soc_uid=soc_uid,
    )

    # If this is a direct HTMX request ('Hx-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so it must be an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)

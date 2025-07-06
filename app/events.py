"""
Page handlers for all things related to events in the `SoCEvent` model.

Attributes:
    events: Microdot_ sub app to handle all events related endpoints. Will be
        mounted on the ``/events`` URL prefix

.. _Microdot: https://microdot.readthedocs.io/en/latest/index.html
"""

from microdot.asgi import Microdot, redirect
from microdot.utemplate import Template
from app.models.data import (
    getUnallocatedEvents,
    delUnallocBatEvents,
    delDanglingEvents,
    delBatUIDEvents,
    delExtraSoCEvent,
    getBatUnallocSummary,
)
from app.models.utils import measureSummary, setCapacityFromSocUID


from .index import (
    renderIndex,
    errorResponse,
)

# The base URL for this sub app. This should be without the trailing /
BASE_URL = "/events"

# Creates the events handler sub app.
events = Microdot()


@events.get("/")
async def allEvents(req):
    """
    Returns all events....
    """
    # Get all events
    evts = getUnallocatedEvents()
    content = Template("unallocated_events.html").render(events=evts)

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so it must be an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@events.get("/del_dangling_events")
async def cleanDanglingEvents(req):
    """
    Deletes all events that do not have a battery ID
    """
    # If this did not come in via htmx request, we redirect to the base URL so
    # that we can be sure to always get here from an HTMX get
    if req.headers.get("Hx-Request", "false") == "false":
        return redirect("{BASE_URL}/")

    # Delete unallocated events
    res = delDanglingEvents()

    # If the delete failed for any reason, we flash the error
    if not res["success"]:
        return errorResponse(res["msg"])

    # Delete was successful. Add an Hx-redirect header to cause HTMX to do a
    # browser redirect to the new battery URL
    return "success", 200, {"HX-Redirect": f"{BASE_URL}/"}


@events.get("/<bat_id>/")
async def batEvents(req, bat_id):
    """
    Returns all battery events....
    """
    # Get all events - we get it as a list here since the template needs to
    # know if there are any events at all. It will show a message instead of
    # the list view if there are no events.
    evts = getBatUnallocSummary(bat_id)
    content = Template("events_bat_id.html").render(bat_events=evts, bat_id=bat_id)

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@events.get("/<bat_id>/del_events")
async def delBatEvents(req, bat_id):
    """
    Deletes all unallocated events for this battery....
    """
    # If this did not come in via htmx request, we redirect to the base URL so
    # that we can be sure to always get here from an HTMX get
    if req.headers.get("Hx-Request", "false") == "false":
        return redirect(f"{BASE_URL}/{bat_id}/")

    # Delete unallocated events
    res = delUnallocBatEvents(bat_id)

    # If the delete failed for any reason, we flash the error
    if not res["success"]:
        return errorResponse(res["msg"])

    # Delete was successful. Add an Hx-redirect header to cause HTMX to do a
    # browser redirect to the new battery URL
    return "success", 200, {"HX-Redirect": f"{BASE_URL}/"}


@events.get("/<bat_id>/del_extra/<soc_id>")
async def delExtraEvent(req, bat_id, soc_id):
    """
    Deletes extra "Charging" event that stops us from record a battery
    measurement by UID.

    At times there is a "stray" measurement event just before the "Completed"
    event in a set of measurement events. This one extra events throws the
    `setUIDHistory` call off because it expects a specific sequence of
    measurement events.

    This event is always identifiable as a sincle event in the events group,
    with ``state`` as "Charged" and ``soc_state`` as "Charging". Unfortunately
    there may be more than one of these per cycle, so the
    ``events_bat_id.html`` template will add an link to delete any such
    entries.

    This link brings us here.

    Args:
        req: Microdot request object
        bat_id: The battery ID
        soc_id: The `SoCEvent` ID that needs to be deleted.
    """
    # If this did not come in via htmx request, we redirect to the base URL so
    # that we can be sure to always get here from an HTMX get
    if req.headers.get("Hx-Request", "false") == "false":
        return redirect(f"{BASE_URL}/{bat_id}/")

    # Delete unallocated events
    res = delExtraSoCEvent(bat_id, soc_id)

    if not res["success"]:
        return errorResponse(res["msg"])

    return redirect(f"{BASE_URL}/{bat_id}/")


@events.get("/<bat_id>/<uid>/measure/")
async def uidEvents(req, bat_id, uid):
    """
    Returns all battery uid events....
    """
    # Get a measurement summary as well as the end dis/charge events.
    summary = measureSummary(uid, bat_id, incl_end_events=True)

    if not summary["success"]:
        return errorResponse(summary["msg"])

    content = Template("events_measure.html").render(
        sum=summary, bat_id=bat_id, uid=uid
    )

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content, 200, {"HX-Push-Url": req.url}

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@events.get("/<bat_id>/<uid>/measure/set_history")
async def setUIDHistory(req, bat_id, uid):
    """
    Set the UID events as history events...
    """

    # If this did not come in via htmx request, we redirect to the base URL so
    # that we can be sure to always get here from an HTMX get
    if req.headers.get("Hx-Request", "false") == "false":
        return redirect(f"{BASE_URL}/measure/{bat_id}/{uid}")

    # Here we will do the history allocation
    res = setCapacityFromSocUID(uid, bat_id)

    if not res["success"]:
        return errorResponse(res["msg"])

    # Change was successful. Add an Hx-redirect header to cause HTMX to do a
    # browser redirect to the new battery URL
    return "success", 200, {"HX-Redirect": f"/bat/{bat_id}/{uid}/"}


@events.get("/<bat_id>/<uid>/measure/del_history")
async def delUIDEvents(req, bat_id, uid):
    """
    Deletes the UID events...
    """

    # If this did not come in via htmx request, we redirect to the base URL so
    # that we can be sure to always get here from an HTMX get
    if req.headers.get("Hx-Request", "false") == "false":
        return redirect(f"{BASE_URL}/measure/{bat_id}/{uid}")

    # Here we will do the history allocation
    res = delBatUIDEvents(bat_id, uid)

    if not res["success"]:
        return errorResponse(res["msg"])

    return (
        "<article class='success'>"
        "    <header>Success</header>"
        f"    {res['msg']}"
        "     <br />"
        "     <a href='/events/'>Return to events list view</a>"
        "</atricle>"
    )

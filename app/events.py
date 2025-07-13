"""
Page handlers for all things related to events in the `SoCEvent` model.

Below are some examples of the main views.

.. figure:: img/events_view.png
   :width: 60%
   :align: left

   **Main list view of available unallocated events.**

.. figure:: img/events_bat_id.png
   :width: 60%
   :align: left

   **List of unallocated events for a specific battery ID.**

.. figure:: img/events_assign_hist.png
   :width: 60%
   :align: left

   **View of a single measurement cycle that can be allocated as history or
   deleted.**

   Note: This screenshot was taken for a cycle measure on a BC that was not
   functioning correctly for the charge measures, thus the strange charge
   cycles and negative accuracy.


   From here the measurements time plot can also be viewed.
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
    Generates a view of all `SoCEvent` entries that have not been allocated as
    `BatCapHistory` events yet.

    .. figure:: img/events_view.png
       :width: 60%
       :align: left

    This is the list of raw events that needs to be allocated as history events,
    or removed if not needed.

    Each Battery ID will link through to the `batEvents` view.

    These events are retrieved using the `getUnallocatedEvents` data interface
    and then plugged into the ``unallocated_events.html`` template for display.

    If this was an HTMX request, we only render and return the content HTML. If
    not an HTMX request, it means we need to render the whole page, so we
    return the full page HTML via `renderIndex`, passing the event list view
    content to `renderIndex` to render as the content section.

    Args:
        req: The ``microdot.request`` instance.

    Returns:
        The rendered HTML
    """
    # Get all events
    evts = getUnallocatedEvents()
    content = Template("unallocated_events.html").render(events=evts)

    # If this is a direct HTMX request ('Hx-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so it must be an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@events.get("/del_dangling_events")
async def cleanDanglingEvents(req):
    """
    Allows deletion of all events that do have a battery ID.

    As soon as a battery is inserted in the BC, a battery insertion event wil
    be published but will not have a battery ID yet. Since this is an event, it
    will show up on the `allEvents` view. These are termed *dangling events.*

    The `allEvents` view will have a button to allow deleting all *dangling
    events* which will call this handler after getting confirmation from the
    user.

    These events are then deleted using the `delDanglingEvents` data interface
    and will return a success of error response.

    On success, the UI would redirect back to the `allEvents` view. Or error,
    the error will be flashed on the UI.

    We should only get here from and HTMX request since then we know the user
    has seen these events and have consciously decided to delete them. If not
    an HTMX request, we redirect back to the `BASE_URL`.

    Args:
        req: The ``microdot.request`` instance.

    Returns:
        An error or HTMX redirect.
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
    Generates a view of all unallocated `SoCEvent` entries (does not have a
    `BatCapHistory` entry yet) for a specific battery ID.

    We get here from the `allEvents` view.

    .. figure:: img/events_bat_id.png
       :width: 60%
       :align: left

    Each unique ``SoC UID`` on this page represents a specific measurement
    cycles and can from here be selected to be set as `BatCapHistory` entries
    to capture this measurements cycle for this battery. The ``SoC UID`` will
    go to the `uidEvents` view.

    These events are retrieved using the `getBatUnallocSummary` data interface
    and then plugged into the ``events_bat_id.html`` template for display.

    The view also has a button that allows deleting all events. This will call
    the `delBatEvents` handler.

    If this was an HTMX request, we only render and return the content HTML. If
    not an HTMX request, it means we need to render the whole page, so we
    return the full page HTML via `renderIndex`, passing the event list view
    content to `renderIndex` to render as the content section.

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID pulled from the URL path.

    Returns:
        The rendered HTML
    """
    # Get all events - we get it as a list here since the template needs to
    # know if there are any events at all. It will show a message instead of
    # the list view if there are no events.
    evts = getBatUnallocSummary(bat_id)
    content = Template("events_bat_id.html").render(bat_events=evts, bat_id=bat_id)

    # If this is a direct HTMX request ('Hx-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@events.get("/<bat_id>/del_events")
async def delBatEvents(req, bat_id):
    """
    Called from the `batEvents` view. Allows deleting all unallocated events
    for this battery.

    After allocating measurement cycles events as `BatCapHistory` events,
    there may still be a number of unallocated events left for the battery that
    has nothing to do with any measurement cycles. This handler allows deleting
    these leftover events.

    It also allows deleting any other events with an associated ``SoC UID``.
    This is mostly needed for measurements cycles that may have gone wrong or
    have not completed fully.

    These events are deleted using the `delUnallocBatEvents` data interface
    and will return a success of error response.

    On success, the UI would redirect back to the `allEvents` view. Or error,
    the error will be flashed on the UI.

    We should only get here from and HTMX request since then we know the user
    has seen these events and have consciously decided to delete them. If not
    an HTMX request, we redirect back to the events view for this battery.

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID pulled from the URL path.

    Returns:
        An error or an HTMX redirect.
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

    This event is always identifiable as a single event in the events group,
    with ``state`` as "Charged" and ``soc_state`` as "Charging". Unfortunately
    there may be more than one of these per cycle, so the
    ``events_bat_id.html`` template will add an link to delete any such
    entries.

    This link brings us here.

    Args:
        req: Microdot request object
        bat_id: The battery ID
        soc_id: The `SoCEvent` ID that needs to be deleted.

    Returns:
        An error or a redirect.
    """
    # If this did not come in via HTMX request, we redirect to the base URL so
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
    Generates a view to allow allocating a specific ``SoC UID`` measurement
    cycle to a battery as a `BatCapHistory` entry.

    We get there from the `batEvents` view.

    .. figure:: img/events_assign_hist.png
       :width: 60%
       :align: left

    This view displays a summary of the overall measurement cycle as well as
    the individual cycles making up the overall measurement.

    The view data is obtained from `measureSummary` and is then plugged into
    the ``events_measure.html`` template.

    This view has a button to set the measure event as a `BatCapHistory` events
    which will call the `setUIDHistory` handler.

    It also allows completely deleting this ``SoC UID`` if there is something
    amiss with the measurement. This button will call the `delUIDEvents`
    handler.

    If this was an HTMX request, we only render and return the content HTML. If
    not an HTMX request, it means we need to render the whole page, so we
    return the full page HTML via `renderIndex`, passing the event list view
    content to `renderIndex` to render as the content section.

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID pulled from the URL path.

    Returns:
        An error or an HTMX redirect.
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

    # This is not a direct HTMX request, so it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@events.get("/<bat_id>/<uid>/measure/set_history")
async def setUIDHistory(req, bat_id, uid):
    """
    Called from the `uidEvents` view to capture a specific measurement ``SoC
    UID`` cycles as a battery history event in `BatCapHistory`.

    The `BatCapHistory` entry is created by calling the `setCapacityFromSocUID`
    data interface.

    On success, the UI would redirect to the history view for this recently set
    measurements history event. Or error, the error will be flashed on the UI.

    We should only get here from and HTMX request since then we know the user
    has seen these events and have consciously decided to delete them. If not
    an HTMX request, we redirect back to the `BASE_URL`.

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID pulled from the URL path.
        uid: The ``SoC UID`` pulled from the URL path.

    Returns:
        A redirect instruction for HTMX to go to this history measurement for
        this battery.
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
    Called from the `uidEvents` view to delete all unallocated events for this
    battery ID and ``SoC UID``.

    These events are deleted using the `delBatEvents` data interface
    and will return a success of error response.

    On success, the UI would show a success message. Or error, the error will
    be flashed on the UI.

    We should only get here from and HTMX request since then we know the user
    has seen these events and have consciously decided to delete them. If not
    an HTMX request, we redirect back to the `uidEvents` view.

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID pulled from the URL path.
        uid: The ``SoC UID`` pulled from the URL path.

    Returns:
        An error meessage which is flashed on the UID, or success snippet
        shown in the UI.
    """

    # If this did not come in via htmx request, we redirect to the base URL so
    # that we can be sure to always get here from an HTMX get
    if req.headers.get("Hx-Request", "false") == "false":
        return redirect(f"{BASE_URL}/{bat_id}/{uid}/measure")

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

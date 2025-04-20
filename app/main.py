"""
Main application entry point.
"""

import os
import logging

from microdot.asgi import Microdot, Response, redirect, send_file
from microdot.utemplate import Template
from app.api.docs import app as docs_app
from app.models.data import (
    getUnallocatedEvents,
    delUnallocBatEvents,
    delDanglingEvents,
    delBatUIDEvents,
    getBatUnallocSummary,
    getBatteryDetails,
    getKnownBatteries,
    getBatteryHistory,
    getBatMeasurementByUID,
    getBatMeasurementPlotData,
)
from app.models.utils import measureSummary, setCapacityFromSocUID


from .config import (
    APP_DOCS_PATH,
    MOUNT_APP_DOCS,
    STATIC_DIR,
    VERSION,
)

logger = logging.getLogger(__name__)

# Set the base for our templates
Template.initialize("app/templates")
# Ensure we return text/html as the default application type
Response.default_content_type = "text/html"

app = Microdot()

# Mount the APP API docs?
if MOUNT_APP_DOCS:
    logging.info("Mounting app docs on %s", APP_DOCS_PATH)
    app.mount(docs_app, url_prefix=f"/{APP_DOCS_PATH}")


# app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


@app.get("/")
async def index(_):
    """
    App root.

    We simply render the index.html template
    """
    return Template("index.html").render(content="", version=VERSION)


@app.get("/events/")
async def events(req):
    """
    Returns all events....
    """
    # Get all events
    evts = getUnallocatedEvents()
    content = Template("unallocated_events.html").render(events=evts)

    if req.headers.get("Hx-Request", "false") == "true":
        return content

    return Template("index.html").render(content=content, version=VERSION)


@app.get("/events/del_dangling_events")
async def cleanDanglingEvents(req):
    """
    Deletes all events that do not have a battery ID
    """
    # If this did not come in via htmx request, we redirect to the base URL so
    # that we can be sure to always get here from an HTMX get
    if req.headers.get("Hx-Request", "false") == "false":
        return redirect("/events/")

    # Delete unallocated events
    res = delDanglingEvents()

    # If the change failed:
    if not res["success"]:
        return (
            "<article class='err'>"
            "    <header>Error</header>"
            f"    {res['msg']}"
            "</atricle>"
        )

    return (
        "<article class='success'>"
        "    <header>Success</header>"
        f"    {res['msg']}"
        "</atricle>"
    )


@app.get("events/bat_id/<bat_id>/")
async def batEvents(req, bat_id):
    """
    Returns all battery events....
    """
    # Get all events - we get it as a list here since the template needs to
    # know if there are any events at all. It will show a message instead of
    # the list view if there are no events.
    evts = getBatUnallocSummary(bat_id)
    content = Template("events_bat_id.html").render(bat_events=evts, bat_id=bat_id)

    if req.headers.get("Hx-Request", "false") == "true":
        return content

    return Template("index.html").render(content=content, version=VERSION)


@app.get("events/bat_id/<bat_id>/del_events")
async def delBatEvents(_, bat_id):
    """
    Deletes all unallocated events for this battery....
    """
    # Delete unallocated events
    res = delUnallocBatEvents(bat_id)

    # If the change failed:
    if not res["success"]:
        return (
            "<article class='err'>"
            "    <header>Error</header>"
            f"    {res['msg']}"
            "</atricle>"
        )

    return (
        "<article class='success'>"
        "    <header>Success</header>"
        f"    {res['msg']}"
        "     <br />"
        "     <a href='/events/'>Return to events list view</a>"
        "</atricle>"
    )


@app.get("events/measure/<bat_id>/<uid>/")
async def uidEvents(req, bat_id, uid):
    """
    Returns all battery uid events....
    """
    # Get a measurement summary as well as the end dis/charge events.
    summary = measureSummary(uid, bat_id, incl_end_events=True)

    content = Template("events_measure.html").render(
        sum=summary, bat_id=bat_id, uid=uid
    )

    if req.headers.get("Hx-Request", "false") == "true":
        return content

    return Template("index.html").render(content=content, version=VERSION)


@app.get("events/measure/<bat_id>/<uid>/set_history")
async def setUIDHistory(req, bat_id, uid):
    """
    Set the UID events as history events...
    """

    # If this did not come in via htmx request, we redirect to the base URL so
    # that we can be sure to always get here from an HTMX get
    if req.headers.get("Hx-Request", "false") == "false":
        return redirect(f"/events/measure/{bat_id}/{uid}")

    # Here we will do the history allocation
    res = setCapacityFromSocUID(uid, bat_id)

    # If the change failed:
    if not res["success"]:
        return (
            "<article class='err'>"
            "    <header>Error</header>"
            f"    {res['msg']}"
            "</atricle>"
        )

    # Change was successful. Add an Hx-redirect header to cause HTMX to do a
    # browser redirect to the new battery URL
    return "success", 200, {"HX-Redirect": f"/bat/{bat_id}/{uid}/"}


@app.get("events/measure/<bat_id>/<uid>/del_history")
async def delUIDEvents(req, bat_id, uid):
    """
    Deletes the UID events...
    """

    # If this did not come in via htmx request, we redirect to the base URL so
    # that we can be sure to always get here from an HTMX get
    if req.headers.get("Hx-Request", "false") == "false":
        return redirect(f"/events/measure/{bat_id}/{uid}")

    # Here we will do the history allocation
    res = delBatUIDEvents(bat_id, uid)

    # If the change failed:
    if not res["success"]:
        return (
            "<article class='err'>"
            "    <header>Error</header>"
            f"    {res['msg']}"
            "</atricle>"
        )

    return (
        "<article class='success'>"
        "    <header>Success</header>"
        f"    {res['msg']}"
        "     <br />"
        "     <a href='/events/'>Return to events list view</a>"
        "</atricle>"
    )


@app.get("/bat/")
async def batteries(req):
    """
    Generates the list of known batteries paqe....
    """

    bats = getKnownBatteries()

    content = Template("batteries.html").render(bats=bats)

    if req.headers.get("Hx-Request", "false") == "true":
        return content

    return Template("index.html").render(content=content, version=VERSION)


@app.get("/bat/<bat_id>/")
async def batHistory(req, bat_id):
    """
    Generates ....
    """
    err = None
    hist = None
    # First get the battery current details
    bat = getBatteryDetails(bat_id)
    # We will either 1 or 0 batteries
    if not bat:
        err = f"No battery found with ID {bat_id}"
    else:
        # Get it's history
        hist = getBatteryHistory(bat_id)
        if not hist:
            err = f"No captured history found for battery with ID {bat_id}"

    content = Template("battery_history.html").render(bat=bat, hist=hist, err=err)

    if req.headers.get("Hx-Request", "false") == "true":
        return content

    return Template("index.html").render(content=content, version=VERSION)


@app.get("/bat/<bat_id>/<uid>/")
async def batMeasureUID(req, bat_id, uid):
    """
    Generates ....
    """

    # Get the measurements summary
    summary = getBatMeasurementByUID(bat_id, uid, raw_dates=False)

    if not summary["success"]:
        err = summary["msg"]
        details = None
        cycles = None
    else:
        err = None
        details, cycles = summary["details"], summary["cycles"]

    content = Template("battery_uid_measurement.html").render(
        details=details, cycles=cycles, err=err
    )

    if req.headers.get("Hx-Request", "false") == "true":
        return content

    return Template("index.html").render(content=content, version=VERSION)


@app.get("/bat/<bat_id>/<uid>/plot/<plot_ind>")
async def batMeasureUIDPlot(_, bat_id, uid, plot_ind):
    """
    Generates ....
    """
    # Get the plot data
    plot = getBatMeasurementPlotData(bat_id, uid, plot_ind)

    return plot


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
    return send_file(f_path, max_age=86400)


logging.debug("App starting...")

# We will normally run under behind uvicorn, but if you need to run the local
# Microdot webserver, uncomment this.
# app.run(port=8000, debug=True)

"""
Main application entry point.

Attributes:

    app: The Microdot_ application instance.
    logger: THe module level logger

.. _Microdot: https://microdot.readthedocs.io/en/latest/index.html
"""

import os
import logging
import re
from datetime import datetime

from microdot.asgi import Microdot, Response, Request, redirect, send_file
from microdot.multipart import with_form_data
from microdot.utemplate import Template
from app.api.docs import app as docs_app
from app.models.data import (
    getUnallocatedEvents,
    delUnallocBatEvents,
    delDanglingEvents,
    delBatUIDEvents,
    delExtraSoCEvent,
    getBatUnallocSummary,
    getBatteryImage,
    setBatteryImage,
    delBatteryImage,
    getBatteryDetails,
    getKnownBatteries,
    getBatteryHistory,
    getBatMeasurementByUID,
    getBatMeasurementPlotData,
    getLogs,
    delLogs,
)
from app.models.utils import measureSummary, setCapacityFromSocUID


from .config import (
    APP_DOCS_PATH,
    MOUNT_APP_DOCS,
    STATIC_DIR,
    VERSION,
    THEME_COLOR,
    BAT_IMG_MAX_SZ,
)

# We need to allow for battery images to be uploaded larger than the defaulty
# Microdot content size, so we set the default here.
# See also the batImageSet handler.
Request.max_content_length = int(BAT_IMG_MAX_SZ * 5.5)

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


def errorResponse(msg):
    """
    Any URL handler that needs to flash an error message can call this
    function, passing in the error message and then returning the response
    generated here.

    More details.....

    Args:
        msg: This is either a single string or a list of strings to flash as
            error message(s). If it's a list, it will be render as items in an
            unordered list (<ul>). The message(s) may contain minimal HTML
            markup if needed.
    """
    # Generate the output HTML
    if isinstance(msg, str):
        # A simple error message goes into a div
        html = f'<div class="message">{msg}</div>'
    else:
        # Multiple messages goes into a list
        html = '<ul class="message-list">'
        html += "".join([f"<li>{m}</li>" for m in msg])
        html += "</ul>"

    # Create Microdot Response
    response = Response(body=html)
    # We will change the target for the response to the .error container,
    # overriding any default target from the original request.
    response.headers["HX-Retarget"] = ".err-flash"

    return response


def _renderIndex(content: str = ""):
    """
    Wrapper to render the full index template with optional content.

    Since we are passing certain context to the ``index.html`` template, it is
    better to abstract rendering to one function instead of having to repeat
    the context in all places we render ``index.html``.

    Args:
        content: Any content to render in the content section
    """

    return Template("index.html").render(
        content=content,
        version=VERSION,
        bat_img_max_sz=BAT_IMG_MAX_SZ,
        theme=THEME_COLOR,
    )


@app.get("/")
async def index(_):
    """
    App root.

    We simply render the index.html template
    """
    return _renderIndex()


@app.get("/events/")
async def events(req):
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
    return _renderIndex(content)


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

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return _renderIndex(content)


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


@app.get("events/bat_id/<bat_id>/del_extra/<soc_id>")
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
        return redirect(f"/events/bat_id/{bat_id}/")

    # Delete unallocated events
    res = delExtraSoCEvent(bat_id, soc_id)

    if not res["success"]:
        return errorResponse(res["msg"])

    return redirect(f"/events/bat_id/{bat_id}/")


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

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return _renderIndex(content)


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
    Generates a battery list view.

    All known batteries will be included ordered by battery ID.

    Searching for only specific battery IDs is possibly by adding a 'search'
    query parameter:

        /bat/?search=1234

    If a search string is included, only battery entries where the search
    string is found anywhere in the battery id will be included in the list
    view.
    """
    # Is there a search string? Default to None
    search = None
    if "search" in req.args:
        # The args part is a MultiDict, but it seems that if the value is one
        # element only, then it will be returned not as a list, but as the only
        # element in the list.
        search = req.args["search"]

    bats = getKnownBatteries(search=search)

    content = Template("batteries.html").render(bats=bats)

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return _renderIndex(content)


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

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return _renderIndex(content)


@app.route("/bat/<bat_id>/img", methods=["GET", "DELETE"])
async def batImageGetDel(req, bat_id):
    """
    API endpoint handler to get or delete a battery image.

    * **URL**:      /bat/<bat_id>/img
    * **Methods**: GET, DELETE

    If the HTTP method is *GET*, we return the battery image if available,
    including the correct Content-Type.

    If the method is *DELETE*, we delete the image if the battery ID is valid,
    and return success (200).

    The reason this method handles *GET* and *DELETE* is because the *POST* and
    *PUT* methods are form handlers and needs the additional ``@with_form_data``
    decorator.

    See:
        `batImageSet`

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID as picked from the path

    Returns:
        200 on Success.
        For *GET*, the image data is returned.
    """
    logger.info("Request to %s image for battery %s", req.method, bat_id)

    if req.method == "GET":
        res = getBatteryImage(bat_id)
        # If the result is a string then this is an error.
        if isinstance(res, str):
            return res, 404
        # It must be a BatteryImage instance, return the image with the correct
        # content type set.
        return Response(body=res.image, headers={"Content-Type": res.mime})

    # This must be a DELETE
    res = delBatteryImage(bat_id)
    if res is not True:
        return res, 400

    return "Image deleted", 200


@app.route("/bat/<bat_id>/img", methods=["POST", "PUT"])
@with_form_data
async def batImageSet(req, bat_id):
    """
    API endpoint handler to add or update a battery image.

    * **URL**:      /bat/<bat_id>/img
    * **Methods**: POST, PUT

    This is expected to be a `multipart/form-data`_ *POST* or *PUT* with a
    field named ``image`` as the form part of the image data. This part also
    needs the correct mime type for image to be set in the *Content-Type*
    header for the image part.

    The file field should be named "image" and MUST have a Content-Type
    included.

    For both HTTP methods a new image will be added if one does not exist yet,
    or replaced if one already exists.

    Calls `setBatteryImage` to update the `BatteryImage` record.

    See:
        `batImageGetDel`

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID as picked from the path

    Returns:
        200 if the image was updated.
        201 if the image was created as new.
        400 on invalid battery ID or no image field
        415 if no image content type or not an image type
        413 if the image size is too large
        500 if there was an issue saving the image

    .. _multipart/form-data: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/MIME_types#multipartform-data

    """
    logger.info("Doing a battery image update for bat with ID %s...", bat_id)

    # Get the image part as a file in the request
    img = req.files.get("image")
    if img is None:
        return "image part missing", 400

    # Get the content type from the upload file part as out mime type. We
    # require it to be and image type, or else we exit wit a 415
    mime = getattr(img, "content_type", None)
    if not mime or not mime.startswith("image/"):
        msg = f"Content-Type missing or not an image. Mime: {mime}"
        logging.error(msg)
        return msg, 415

    # We allow a tolerance of 5% larger for the image
    # NOTE: If the image is larger than the Request.max_content_length we set
    # at the top of this module, we will not even get here.
    max_size = int(BAT_IMG_MAX_SZ * 1.05)

    img_dat = await img.read(n=max_size + 1)

    if len(img_dat) >= max_size:
        # Too large
        msg = f"File too large: {len(img_dat)}. Max allowed {BAT_IMG_MAX_SZ}b (+5%)"
        logger.error(msg)
        return msg, 413

    res = setBatteryImage(bat_id, img_dat, mime)
    if not res["success"]:
        if res["not_found"]:
            return res["err"], 400
        return res["err"], 500

    if res["new"]:
        return "New image set", 201

    return "Image updated", 200


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

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return _renderIndex(content)


@app.get("/bat/<bat_id>/<uid>/plot/<plot_ind>")
async def batMeasureUIDPlot(_, bat_id, uid, plot_ind):
    """
    Generates ....
    """
    # Get the plot data
    plot = getBatMeasurementPlotData(bat_id, uid, plot_ind)

    return plot


@app.get("/logs/")
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
    return _renderIndex(content)


@app.route("/logs/cleanup", methods=["POST"])
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
        return redirect("/logs/")

    before_date = req.form.get("before_date")
    # Check if the format matches the expected timestamp pattern
    ts_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
    if not re.match(ts_pattern, before_date):
        return errorResponse(f"Invalid timestamp format: {before_date}")

    # Convert the string to a datetime object if valid
    try:
        before_date = datetime.strptime(before_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return errorResponse(f"Invalid timestamp value: {before_date}")

    logging.info("  Logs before %s to deleted", before_date)

    res = delLogs(before_date)

    if not res["success"]:
        return errorResponse(res["msg"])

    logging.info("  Logs delete result: %s", res)
    # Redirect to '/logs/'
    # Because the request came from HTMX, we need to handle the redirect
    # differently, or else the redirect URL will not be followed as a new page
    # request
    response = Response(status_code=302)
    response.headers["HX-Redirect"] = "/logs/"
    return response


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

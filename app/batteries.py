"""
Page handlers for batteries in the `Battery`, `BatCapHistory` and
`BatteryImage` models.

Below are some examples of the main views.

.. figure:: img/batteries_list.png
   :width: 60%
   :align: left

   **Main list view of available batteries.**

.. figure:: img/battery_view.png
   :width: 60%
   :align: left

   **Battery view showing capacity and measurement history.**

.. figure:: img/battery_capacity.png
   :width: 60%
   :align: left

   **Battery Capacity Measurement view showing capacity and measurement cycles.**

   From here the measurements time plot can also be viewed.

-----------


Attributes:
    bat: Microdot_ sub app to handle all battery related endpoints. Will be
        mounted on the ``/bat`` URL prefix
    logger: Local module logger.
    BASE_URL: Constant for the base URL path for the `bat` app.

              The `main` module will import both `bat` and `BASE_URL` to mount
              this app on the given URL base path.

.. _Microdot: https://microdot.readthedocs.io/en/latest/index.html
"""

import logging

from microdot.asgi import Microdot, Response
from microdot.multipart import with_form_data
from microdot.utemplate import Template

from app.models.data import (
    getBatteryImage,
    setBatteryImage,
    delBatteryImage,
    getBatteryDimensions,
    getBatteryDetails,
    getKnownBatteries,
    getBatteryHistory,
    getBatMeasurementByUID,
    getBatMeasurementPlotData,
)

from .config import (
    BAT_IMG_MAX_SZ,
)

from .index import (
    renderIndex,
)

# Our local logger
logger = logging.getLogger(__name__)

# The base URL for this sub app. This should be without the trailing /
BASE_URL = "/bat"

# Creates the events handler sub app.
bat = Microdot()


@bat.get("/")
async def batteries(req):
    """
    Generates the main `Battery` list view.

    All known batteries will be included ordered by `Battery` ID.

    Searching for only specific battery IDs is possibly by adding a ``search``
    query parameter::

        /bat/?search=1234

    If a search string is included, only battery entries where the search
    string is found anywhere in the battery id will be included in the list
    view.

    This function uses the `getKnownBatteries` data interface to get a list of
    all the `Battery` entries and related info. This is then plugged into the
    ``batteries.html`` template to render the batteries content section view.

    If this was an HTMX request, we only render and return the content HTML. If
    not an HTMX request, it means we need to render the whole page, so we
    return the full page HTML via `renderIndex`, passing the battery list view
    content to `renderIndex` to render as the content section.

    Args:
        req: The ``microdot.request`` instance.

    Returns:
        The rendered HTML
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
    return renderIndex(content)


@bat.get("/knownDims")
async def knownBatteryDimension(req):
    """
    Returns a list of all known unique `Battery.dimension` values by calling
    `getBatteryDimensions`.

    The default is to return these as an HTML snippet for swapping into a
    ``<datalist>`` element. THis ``<datalist>`` would then normally be linked
    to and ``<input>`` element (via the input's ``list`` attribute. The input
    would normally be a test input which allows entering new values, or
    selecting one from the linked ``<datalist>`` options.

    The other option is return a JSON list of dimension.

    This output format is controller by a ``format`` query option
    like in ``../?format=list`` with these options:

    * ``datalist``: The default and returns ``application/html`` content type
      as::

        <option value="18650"></option>
        <option value="P055780"></option>

    * ``list``: Returns it a list of strings in JSON format with
      ``application/json`` as content type.

    Invalid format values will result in a 400 error.

    Args:
        req: The request object, optionally with a ``format`` element in
            ``req.args`` if using the ``...?format=???`` query arg.

    Returns:
        See above
    """
    # Get the output format, defaulting to `datalist`
    fmt = req.args.get("format", "datalist")

    # Validate the format
    if fmt not in ["datalist", "list"]:
        return f"Invalid output format: {fmt}", 400

    # Get the dimension
    dims = getBatteryDimensions()

    # For a list format, we can return the result as is - Microdot will auto
    # add the application/json content type
    if fmt == "list":
        return dims

    # For now the only other option is the data list format
    # We create a string of lines as <option value='{dim}'></option> with each
    # line terminated by a newline.
    # Microdot will auto set the content type to text/html
    return "\n".join(f'<option value="{d}"></option>' for d in dims)


@bat.get("/<bat_id>/")
async def batHistory(req, bat_id):
    """
    Generates the `Battery` details and measurements history view.

    This function uses the `getBatteryDetails` data interface to get the
    `Battery` details for the battery ID in the URL path.

    The `Battery` measurement history is retrieved via the `getBatteryHistory`
    data interface.

    The battery and history details are then plugged into the
    ``battery_history.html`` template to render the content HTML.

    If this was an HTMX request, we only render and return the content HTML. If
    not an HTMX request, it means we need to render the whole page, so we
    return the full page HTML via `renderIndex`, passing the battery list view
    content to `renderIndex` to render as the content section.

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID pulled from the URL path.

    Returns:
        The rendered HTML
    """
    err = None
    hist = None
    # First get the battery current details
    batt = getBatteryDetails(bat_id)
    # We will either 1 or 0 batteries
    if not batt:
        err = f"No battery found with ID {bat_id}"
    else:
        # Get it's history
        hist = getBatteryHistory(bat_id)
        if not hist:
            err = f"No captured history found for battery with ID {bat_id}"

    content = Template("battery_history.html").render(bat=batt, hist=hist, err=err)

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@bat.route("/<bat_id>/img", methods=["GET", "DELETE"])
async def batImageGetDel(req, bat_id):
    """
    API endpoint handler to get or delete a `BatteryImage` for a given
    `Battery`.

    HTTP methods allowed: ``GET``, ``DELETE``

    If the HTTP method is ``GET``, we return the battery image if available,
    including the correct ``Content-Type``.

    If the method is ``DELETE``, we delete the image if the battery ID is valid,
    and return success (200).

    The reason this method handles ``GET`` and ``DELETE`` is because the
    ``POST`` and ``PUT`` methods are form handlers and needs the additional
    ``@with_form_data`` decorator, adding more unneeded complexity

    It used the `getBatteryImage` data interface to retrieve the image for the
    battery ID found in the URL path.

    The `delBatteryImage` data interface is used to delete the image.

    See:
        `batImageSet` for how the image is added for a given battery.

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


@bat.route("/<bat_id>/img", methods=["POST", "PUT"])
@with_form_data
async def batImageSet(req, bat_id):
    """
    API endpoint handler to add or update a `BatteryImage` for a given
    `Battery`.

    HTTP methods allowed: ``PUT``, ``POST``

    This is expected to be a `multipart/form-data`_ ``POST`` or ``PUT`` with a
    field named ``image`` as the form part of the image data. This part also
    needs the correct mime type for image to be set in the *Content-Type*
    header for the image part.

    The file field should be named "image" and MUST have a ``Content-Type``
    included.

    For both HTTP methods the image will be added or replaced using the
    `setBatteryImage` data interface function.

    Note:
        Images are limited to `BAT_IMG_MAX_SZ` with a small tolerance.

    See:
        `batImageGetDel` for retrieving the `BatteryImage`

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID as picked from the path

    Returns:
        * 200 if the image was updated.
        * 201 if the image was created as new.
        * 400 on invalid battery ID or no image field
        * 415 if no image content type or not an image type
        * 413 if the image size is too large
        * 500 if there was an issue saving the image

    .. _multipart/form-data: https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/MIME_types#multipartform-data

    """
    # This is a busy little function, so @pylint: disable=too-many-return-statements

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


@bat.get("/<bat_id>/<uid>/")
async def batMeasureUID(req, bat_id, uid):
    """
    Generates the `Battery` measurement details for a specific measurement UID
    for the battery in the `BatCapHistory` table.

    This function uses the `getBatMeasurementByUID` data interface to get
    the `BatCapHistory` details for the battery ID and UID in the URL path.

    The measurement details are then plugged into the
    ``battery_uid_measurement.html`` template to render the content HTML.

    If this was an HTMX request, we only render and return the content HTML. If
    not an HTMX request, it means we need to render the whole page, so we
    return the full page HTML via `renderIndex`, passing the battery list view
    content to `renderIndex` to render as the content section.

    Args:
        req: The ``microdot.request`` instance.
        bat_id: The battery ID pulled from the URL path.
        uid: The measurement UID pulled from the URL path.

    Returns:
        The rendered HTML
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
    return renderIndex(content)


@bat.get("/<bat_id>/<uid>/plot/<plot_ind>")
async def batMeasureUIDPlot(_, bat_id, uid, plot_ind):
    """
    API endpoint called to generate the plot data for a specific `Battery` and
    measurement UID.

    The UI view will use this plot data to render a plot of the measurement
    over time like in the example plot below.

    .. figure:: img/charge_cycle_plot_sample.png
       :width: 40%
       :align: left

       **Sample plot showing the Charge Cycle for one measurement cycle**

    Args:
        _: The discarded ``microdot.request`` instance.
        bat_id: The battery ID pulled from the URL path.
        uid: The measurement UID pulled from the URL path.
        plot_ind: The specific plot indicator. This is the ``plot_ind`` found in
            the ``cycles`` entry as returned by `getBatMeasurementByUID`. The
            `batMeasureUID` view will render this plot indicator as an anchor
            tag in the content to call this endpoint to fetch the plot data.

    Returns:
        The `getBatMeasurementPlotData` plot points.
    """
    # Get the plot data
    plot = getBatMeasurementPlotData(bat_id, uid, plot_ind)

    return plot

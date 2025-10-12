"""
Page handlers for battery packs in the `BatteryPack` model.

Below are some examples of the main views.

.. figure:: img/bat_packs_list.png
   :width: 60%
   :align: left

   **Main list view of available battery packs.**

.. figure:: img/bat_pack_build.png
   :width: 60%
   :align: left

   **View showing how a battery pack is built.**

-----------


Attributes:
    pack: Microdot_ sub app to handle all battery pack related endpoints. Will
        be mounted on the ``/pack`` URL prefix
    logger: Local module logger.
    BASE_URL: Constant for the base URL path for the `pack` app.

              The `main` module will import both `pack` and `BASE_URL` to mount
              this app on the given URL base path.

.. _Microdot: https://microdot.readthedocs.io/en/latest/index.html
"""

import logging
import json
import copy

from microdot.asgi import Microdot
from microdot.utemplate import Template

from app.models.data import (
    getPacks,
    getPack,
    convertIDs,
    getAvailable,
    build,
    savePack,
)

from .index import (
    renderIndex,
    flashMessage,
)

# Our local logger
logger = logging.getLogger(__name__)

# The base URL for this sub app. This should be without the trailing /
BASE_URL = "/pack"

# Creates the events handler sub app.
pack = Microdot()


@pack.get("/")
async def packsView(req):
    """
    Generates the main `BatteryPack` list view.

    All known batteries will be included ordered by `Battery` ID.

    Searching for only specific pack names is possibly by adding a ``search``
    query parameter::

        /pack/?search=abc

    If a search string is included, only packs where the search string is found
    anywhere in the pack name will be included in the list view.

    This function uses the `getPacks` data interface to get a list of all the
    `BatteryPack` entries. This is then plugged into the ``bat_packs.html``
    template to render the content section view.

    If this was an HTMX request, we only render and return the content HTML. If
    not an HTMX request, it means we need to render the whole page, so we
    return the full page HTML via `renderIndex`, passing the battery pack list
    view content to `renderIndex` to render as the content section.

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

    packs = getPacks(search=search)

    content = Template("bat_packs.html").render(packs=packs)

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


def packView(req, pack_id=None):
    """
    Generates the view for creating a new pack or editing an existing one.

    This is called from the `existingPack` or `newPack` URL handlers only for
    GET requests.

    This function will prepare the initial pack view page for an existing
    (``pack_is`` is set) or new pack (``pack_id`` is None).

    It populates the `bat_pack_build_html` template once the pack info has been
    gathered.
    """
    # Get the pack by ID, and if no ID is available (new pack), returns an
    # empty pack def
    b_pack = getPack(pack_id)

    # Get the batteries that are available to still add to this pack. Exclude
    # all IDs already in the pack
    available = getAvailable(excl=b_pack["config"]["conn"])

    # We need to get the IDs in the pack into a pack_struct which includes the
    # battery details as a dict. This is done by first copying the current
    # connection structure IDs and then replacing the IDs with their battery
    # details dicts.
    pack_conn = copy.deepcopy(b_pack["config"]["conn"])
    # Now we can replace the IDs
    convertIDs(pack_conn)

    logger.info(" Converted pack_conn: %s", pack_conn)

    # Generate the template. We pass the json encoder into the template so that
    # it can be used to encode the config as a JSON string when saving in the
    # template hidden field.
    content = Template("bat_pack_build.html").render(
        pack=b_pack,
        extra=[],
        pack_conn=pack_conn,
        pack_extra=[],
        avail=available,
        json=json,
    )

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


def packSave(req, pack_id):
    """
    Called when the pack needs to be saved.

    Extracts the required from fields and then calls `savePack` to save the
    `BatteryPack` and updates all `Battery.pack` fields involved.

    On success, it will redirect to the pack build view page.
    """
    # Save the pack given the info we have in the form
    res = savePack(
        pack_id,
        req.form["name"],
        req.form["desc"],
        req.form["voltage"],
        req.form["capacity"],
        json.loads(req.form["config"]),
        None,  # Not catering for notes yet.
    )

    # If the save failed for any reason, we flash the error
    if not res["success"]:
        return flashMessage(res["msg"], "error")

    # Save was successful. Add an Hx-redirect header to cause HTMX to do a
    # browser redirect to the Pack URL
    return "success", 200, {"HX-Redirect": f"{BASE_URL}/build/{res['pack'].id}/"}


def packUpdate(req, pack_id=None):
    """
    Updates the pack config and/or saves a completed pack.

    This function is called from both the `existingPack` and `newPack` URL
    handlers. These handlers are there for the pack build URLs, both with, and
    without an existing pack ID. All this means is that we will be called with
    or without a pack ID.

    The call here will always be a form POST and the form will have the
    following form fields:

    * ``name``: The pack name - may be empty for new new packs. Maps to
      `BatteryPack.name`
    * ``desc``: Optional pack description. Maps to `BatteryPack.desc`
    * ``voltage``: The desired pack voltage in mV as a multiple of
      `BatteryPack.NOM_V`. Maps to `BatteryPack.voltage`
    * ``config``: The pack connection config. This comes from a hidden field
      we use to manage the config between HTTP calls. This comes in a JSON
      field which is converted to a dict. Maps to `BatteryPack.config`
    * ``extra``: This comes in a JSON string as a list of battery ids that have
      been selected to be included in the pack, but due to the current pack
      configuration, they can not yet be included until enough are available
      to fill a serial string. We convert this to a list and it is used when
      reevaluating the pack config if this POST adds or removes batteries.
    * ``capacity``: The capacity that was calculated for the current pack
      ``config``.
    * ``action``: If present, it indicates that a pack reconfiguration needs to
      be made. Either the pack voltage has changed, or batteries have been
      added or removed. This will cause the requested action to be taken and
      then the full pack will be reconfigured based on the action result. The
      value can be one of the following:

        * ``v_change``: The pack voltage selection was changed.
        * ``add``: A battery from the list of available batteries was added to
          the pack. The ID for the battery will be in the ``bid`` form field.
        * ``rem``: A battery was removed from the pack. This can either be a
          battery in the current pack ``config``, or from the ``extra`` list.
          The ID for the battery will be in the ``bid`` form field.

    * ``bid``: This will be in the field list if and ``action`` of ``rem`` or
      ``add`` has occurred. See above.
    * ``save``: If present it means the **Save** button was clicked and the
      pack config will now be saved or created if it's a new pack.

    Args:
        req: The ``Microdot`` request object. The ``req.form`` holds all the
            form fields received.
        pack_id: The current `BatteryPack` ID being edited, or ``None`` for a
            new pack.

    Returns:
        The rendered `bat_pack_build_html` template.

    """
    logger.info(" Pack form data: %s", req.form)

    # Get the pack by ID, and if no ID is available (new pack), returns an
    # empty pack def
    b_pack = getPack(pack_id)

    # Update all we can from the received form
    b_pack["name"] = req.form["name"] or None
    b_pack["desc"] = req.form["desc"] or None
    b_pack["voltage"] = int(req.form["voltage"])
    b_pack["config"] = json.loads(req.form["config"])
    logger.info(" Pack general info updated: %s", b_pack)

    # If this is a save, we go save the pack and return
    if "save" in req.form:
        return packSave(req, pack_id)

    # Pick up any extra we still need to add
    extra = json.loads(req.form["extra"])

    # If a battery was added or removed, there would be an `action` element in
    # the form, and it's value will be 'add' or 'del'. In addition there will
    # then be a 'bid' element which will be the battery id to add or remove.
    # A pack voltage change will also post and update with an action of
    # "v_change".
    # Let's handle that now.
    if "action" in req.form:
        # We will need to call the build function, but we need to flatten the
        # current list of ids in the pack connection list first.
        bat_ids = [bid for serial in b_pack["config"]["conn"] for bid in serial]
        # And add anything in the extra list
        bat_ids += extra
        logger.info(" Initial flattened ID list (incl extra): %s", bat_ids)

        if req.form["action"] == "v_change":
            logger.info("Changing pack voltage...")
        else:
            logger.info(
                " Going to %s battery id %s to/from pack.",
                req.form["action"],
                req.form["bid"],
            )

            # extract the battery id to add or remove and convert to an int
            bid = int(req.form["bid"])

            # Add or remove?
            if req.form["action"] == "add":
                # Append to the list
                bat_ids.append(bid)
            else:
                # We need to remove. First check if it is there
                if not bid in bat_ids:
                    # TODO: Surface this to the UI
                    err = (
                        f"Battery ID [{bid}] can not be removed because "
                        f"it does not exist in the current pack: {bat_ids}"
                    )
                    raise ValueError(err)
                bat_ids.remove(bid)

        # Build with the new battery list or updated voltage. We only want IDs
        # for batteries in
        # all lists.
        res = build(bat_ids, b_pack["voltage"], id_only=True)
        logger.info(" Build result: %s", res)

        # TODO: If we get unused or invalid ids returned in res here, we need to
        # surface this to the UI somehow.

        # Now we need to update our b_pack again.
        # First the capacity
        b_pack["capacity"] = res["capacity"]
        # And the config
        b_pack["config"] = res["config"]

        # .. and any left over batteries
        extra = res["extra"]

    # Now get the list of available batteries to choose from.
    # We need to also take the list of extra batteries into account - they
    # should be excluded from the available list. The easiest to get
    # this done is to tack this list on to the end of the config.conn list
    # when we call getAvailable. This works because getAvailable will
    # flatten the list batteries to exclude.
    available = getAvailable(excl=b_pack["config"]["conn"] + [extra])

    # We need to get the IDs in the pack into a pack_struct which includes the
    # battery details as a dict. This is done by first copying the current
    # connection structure IDs and then replacing the IDs with their battery
    # details dicts.
    pack_conn = copy.deepcopy(b_pack["config"]["conn"])
    # Now we can replace the IDs
    convertIDs(pack_conn)
    # And the same for the extra
    pack_extra = copy.deepcopy(extra)
    convertIDs(pack_extra)

    # Generate the template. We pass the json encoder into the template so that
    # it can be used to encode the config as a JSON string when saving in the
    # template hidden field.
    content = Template("bat_pack_build.html").render(
        pack=b_pack,
        extra=extra,
        pack_conn=pack_conn,
        pack_extra=pack_extra,
        avail=available,
        json=json,
    )

    # If this is a direct HTMX request ('Hs-request' header == 'true') then we
    # only refresh the target DOM element with the rendered template.
    if req.headers.get("Hx-Request", "false") == "true":
        return content

    # This is not a direct HTMX request, so we it must an attempt to render the
    # full URL, so we render the full site including the part template.
    return renderIndex(content)


@pack.route("/build/", methods=["GET", "POST"])
async def newPack(req):
    """
    Managing a new pack.

    This is just a wrapper for the endpoint without the ``pack_id``.

    We simply return the results from calling `packView` or `packUpdate`
    depending if this is a GET or POST
    """
    if req.method == "GET":
        return packView(req)

    return packUpdate(req)


@pack.route("/build/<int:pack_id>/", methods=["GET", "POST"])
async def existingPack(req, pack_id=None):
    """
    Managing an existing pack.

    This is just a wrapper for the endpoint with the ``pack_id``.

    We simply return the results from calling `packView` or `packUpdate`
    depending if this is a GET or POST
    """
    if req.method == "GET":
        return packView(req, pack_id)

    return packUpdate(req, pack_id)

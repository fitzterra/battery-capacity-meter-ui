"""
Data interface between API/Web endpoints and the raw data related to battery
data.

Attributes:
    logger: A logger instance for the local module.
"""

import io
import logging

from typing import Iterable
from peewee import fn, JOIN, Case, Value

from PIL import Image

from app.utils import datesToStrings

from ..models import db, Battery, BatteryImage, BatCapHistory, BatteryPack

logger = logging.getLogger(__name__)

__all__ = [
    "getBatteryDimensions",
    "getKnownBatteries",
    "getBatteryDetails",
    "getBatteryHistory",
    "getBatteryImage",
    "setBatteryImage",
    "delBatteryImage",
    "getBatMeasurementByUID",
    "getBatMeasurementPlotData",
]


def getBatteryDimensions() -> list:
    """
    Returns list of unique values from `Battery.dimension` for use in
    selection lists, etc.

    Returns:
        A list like:

        .. python::
            [
                '18650',    # Cylinder, 18mm dia, 650mm high
                'P055780',  # Prismatic (rectangular) 5mm thick, 57x80 mm
            ]

    """
    with db.connection_context():
        query = (
            Battery.select(Battery.dimension)
            .distinct()
            .where(Battery.dimension != None)
            .order_by(Battery.dimension)
        )

        # We return the results as tuples, but then have to pick out the first
        # (only) element to flatten this into a list of sizes.
        return [d[0] for d in query.tuples()]


def getKnownBatteries(
    raw_dates: bool = False, search: str | None = None
) -> Iterable[dict]:
    """
    Generator that returns all known batteries from the `Battery` table.

    Each entry will also including a count of how many history entries each
    has, if it has an image, and if it belongs to a `BatteryPack`, the pack ID
    and the pack name.

    Args:
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.
        search: If supplied, it must be a string that will be used as a LIKE
            SQL search on the battery ID. Only entries where this search match
            will be returned. May be an empty list.

    .. note::
        The ``has_img`` field is a bool to indicate if this battery has an
        image in `BatteryImage`.

        If ``True``, the UI can use whatever URL renders the battery images to
        show the image. This should be something like ``/bat/{bat_id}/img``.

        If ``False``, then no image is available to render.

    .. note::
        The ``pack`` field will be the `BatteryPack` ID or ``None``.

        The ``pack_name`` field will also be empty if the battery does not belong
        to a pack.

    Yields:
        Dictionary entries like:

        .. python::
            {'id': 24,
              'created': '2025-05-03 11:42:57',
              'modified': '2025-05-03 11:42:57',
              'bat_id': '2025050202',
              'cap_date': '2025-05-12',
              'mah': 1393,
              'accuracy': 98,
              'has_img': True/False,
              'h_count': 2,
              'pack': 2,
              'pack_name': 'USB 5V pack for quick charge',},

    """
    with db.connection_context():
        query = (
            Battery.select(
                Battery,
                Case(
                    None,
                    (
                        (
                            # Image is NOT NULL
                            BatteryImage.battery.is_null(False),
                            # Then True, there is an image
                            True,
                        ),
                    ),
                    # Else, False, there is no image
                    False,
                ).alias("has_img"),
                fn.COUNT(BatCapHistory.id).alias("h_count"),
                BatteryPack.name.alias("pack_name"),
            )
            # Join BatteryPack (one-to-many)
            .join(BatteryPack, JOIN.LEFT_OUTER)
            # Switch back to Battery before joining BatteryImage
            .switch(Battery)
            # Join image table first (one-to-one, so no row multiplication)
            .join(BatteryImage, JOIN.LEFT_OUTER)
            # Switch join context back to Battery for history aggregation
            .switch(Battery)
            .join(BatCapHistory, JOIN.LEFT_OUTER)
            .group_by(Battery.id, BatteryImage.battery, BatteryPack.id)
            .order_by(Battery.bat_id)
        )

        # Any search criteria?
        if search:
            query = query.where(Battery.bat_id % f"%{search}%")

        # Return the results, but convert any datetime type elements in the result
        # to date/time strings if raw_dates is false
        for row in query.dicts():
            if raw_dates:
                yield row
            else:
                yield datesToStrings(row)


def getBatteryDetails(bat_id: str, raw_dates: bool = False) -> dict:
    """
    Returns the `Battery` details entry for the given battery ID.

    Args:
        bat_id: The `Battery.bat_id` to retrieve the `Battery` entry for.
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.

    Returns:
        None if no entry found, or a dict representation of the `Battery`
        entry.
    """

    with db.connection_context():
        bat = Battery.select().where(Battery.bat_id == bat_id)
        # We will either 1 or 0 batteries
        if not bat.count():
            return None

        # Get the battery entry as a dictionary
        bat_dict = bat.dicts().get()
        # Does it have an image?
        bat_dict["has_image"] = bat.get().images.count() != 0

        # Return the raw entry if raw_dates is True
        if raw_dates:
            return bat_dict

        # Else convert the dates to strings before returning the dict
        return datesToStrings(bat_dict)


def getBatteryHistory(bat_id: str, raw_dates: bool = False) -> Iterable[dict]:
    """
    Generator that returns all capture history events available for a given
    battery ID.

    This is the SQL we execute:

    .. code::

        select
            b.bat_id,
            h.cap_date,
            h.bc_name,
            h.soc_uid,
            h.mah,
            h.accuracy,
            h.num_events
        from battery b
            inner join bat_cap_history h ON h.battery_id = b.id
        where b.bat_id = '<bat_id>'
        order by b.cap_date desc

    which may a result as::

        +------------+------------+-----------+----------+------+----------+------------+
        | bat_id     | cap_date   | bc_name   | soc_uid  | mah  | accuracy | num_events |
        |------------+------------+-----------+----------+------+----------+------------|
        | 2025030501 | 2025-03-05 | BC0       | 28dac6f2 | 1838 | 99       | 57062      |
        +------------+------------+------------+----------+------+----------+------------+

    Args:
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.

    Yields:
        ``dict``: Each entry as a dictionary as follows::

            {
                'bat_id': '2025030501',
                'cap_date': "2025-03-05",

                # Or with raw_dates == True
                # 'cap_date': datetime.date(2025, 3, 5),

                'bc_name': "BC0",
                'soc_uid': '28dac6f2',
                'mah': 1838,
                'accuracy': 99,
                'num_events': 57062
            }
    """

    with db.connection_context():
        query = (
            Battery.select(
                Battery.bat_id,
                BatCapHistory.cap_date,
                BatCapHistory.bc_name,
                BatCapHistory.soc_uid,
                BatCapHistory.mah,
                BatCapHistory.accuracy,
                BatCapHistory.num_events,
            )
            .join(BatCapHistory)
            .where(Battery.bat_id == bat_id)
            # Order descending on capture date so we get the newest first.
            .order_by(BatCapHistory.cap_date.desc())
        )

        # Return the results, but convert any datetime type elements in the result
        # to date/time strings if raw_dates is false
        for row in query.dicts():
            if raw_dates:
                yield row
            else:
                yield datesToStrings(row)


def getBatteryImage(bat_id: str):
    """
    Returns the raw image for the battery with given ID.

    Args:
        bat_id: The `Battery.bat_id` to retrieve the `BatteryImage` entry for.

    Returns:
        An error string if the battery is not found or it does not have an
        image.
        A `BatteryImage` instance if found.
    """
    with db.connection_context():
        bat = Battery.select().where(Battery.bat_id == bat_id)
        # We will either 1 or 0 batteries
        if not bat.count():
            err = f"Battery with ID {bat_id} not found."
            logger.debug(err)
            return err

        # Get the battery instance
        bat = bat.get()

        # If there are no images linked to this battery, return None
        if not bat.images.count():
            err = f"No image found for battery with ID {bat_id}"
            logger.debug(err)
            return err

        # Return the image instance
        logger.debug("Image found for battery with ID: %s", bat_id)
        return bat.images.get()


def setBatteryImage(bat_id: str, img_dat: bytes, mime: str) -> dict:
    """
    Sets or updates image for the given battery ID.

    Args:
        bat_id: The `Battery.bat_id` to create or update the `BatteryImage`
            entry for.
        img_dat: The raw image data as bytes.
        mime: The mime type for the image

    Returns:
        A dictionary:

        .. python::
            {
                'success': bool,
                'not_found': True if success is false and the battery was not found,
                'new': If success is True, this is True if a new image was added,
                    False for an update,
                'err': If success is False, this is an error message for the reason
            }
    """
    res = {"success": False, "not_found": False, "new": None, "err": None}

    with db.connection_context():
        bat = Battery.select().where(Battery.bat_id == bat_id)
        # We will either 1 or 0 batteries
        if not bat.count():
            res["err"] = f"Battery with ID {bat_id} not found."
            res["not_found"]: True
            logger.debug(res["err"])
            return res

        # Get the battery instance
        bat = bat.get()

        try:
            # Load image just to extract dimensions (no need to decode full pixel data)
            with Image.open(io.BytesIO(img_dat)) as img:
                width, height = img.size
            # Get the size
            size = len(img_dat)

            # If there are no images linked to this battery, we create a new
            # one
            if not bat.images.count():
                logger.debug("Creating new image for battery with ID %s.", bat_id)
                img = BatteryImage.create(
                    battery=bat,
                    image=img_dat,
                    mime=mime,
                    size=size,
                    width=width,
                    height=height,
                )
                res["new"] = True
            else:
                logger.debug("Updating image for battery with ID %s.", bat_id)
                # Get the image
                img = bat.images.get()
                # ... and update and save
                img.image = img_dat
                img.mime = mime
                img.size = size
                img.width = width
                img.height = height
                img.save()
                res["new"] = False
        except Exception as exc:
            res["err"] = "Error updating/creating image. See logs for details."
            logger.error("Error creating image for bat with ID %s : %s", bat_id, exc)
            return res

        res["success"] = True

        return res


def delBatteryImage(bat_id: str):
    """
    Deletes a battery image.

    Args:
        bat_id: The `Battery.bat_id` to delete the `BatteryImage` entry for.

    Returns:
        An error string if the battery is not found, or there was an error
        deleting it.
        True if the delete was successful, even if the battery has no image.
    """
    with db.connection_context():
        bat = Battery.select().where(Battery.bat_id == bat_id)
        # We will either 1 or 0 batteries
        if not bat.count():
            err = f"Battery with ID {bat_id} not found."
            logger.debug(err)
            return err

        # Get the battery instance
        bat = bat.get()

        # There is no image linked to this battery, so indicate success
        if not bat.images.count():
            logger.debug("No image found to delete for battery with ID %s", bat_id)
            return True

        # Return the image instance
        logger.debug("Deleting image for battery with ID: %s", bat_id)
        try:
            img = bat.images.get()
            img.delete().execute()
        except Exception as exc:
            logger.error("Error deleting image for battery %s - Error: %s", bat, exc)
            return f"Error deleting battery image for battery with ID {bat_id}"

        return True


def getBatMeasurementByUID(bat_id: str, uid: str, raw_dates: bool = False) -> dict:
    """
    Returns battery and capacity measurement info for a specific measurement
    UID for a given `Battery.bat_id`.

    The measurement UID is a `BatCapHistory.soc_uid` for an entry linked to
    this `Battery`.

    .. note::
        The query will use a join from `Battery.id` to `BatCapHistory.battery`
        which means the given ``uid`` must be for the given ``bat_id``.

    This function should be used when the measurement info like date, capacity,
    etc., as well as a list of the dis/charge cycles making up the capacity
    measurement, needs to be surfaced.

    It returns a dictionary as follows:

    .. python::
        {
            'success': True,
            'msg': '',
            'details': {
                 'bat_id': '2025020101',
                 'uid': 'c22729fc',
                 'cap_date': '2025-02-01 16:46:07',
                 'mah': 2344,
                 'accuracy': 80,
                 'shunt': {
                    'ch': 1.3,  # Charge shunt resistor value in ohms
                    'dch': 8.5, # Discharge shunt resistor value in ohms
                 },
                 'bc_name': 'BC0'},
            'cycles': [
                {
                    'timestamp': '2025-02-01 17:18:16',
                    'bc_name': 'BC0',
                    'state': 'Charged',
                    'bat_id': '2025020101',
                    'bat_v': 4183,
                    'mah': 135,
                    'period': 1928,
                    'soc_state': 'Resting',
                    'cycle': '1/2',
                    'plot_ind': 'c0'
                },
                .
                .
                .
            ]
        }

    If there are any errors, the ``success`` value will be ``False`` and the
    ``msg`` value will be an error message that can be surfaced to the user.
    In this case, the ``details`` and ``cycles`` value will be undefined.

    On success, ``details`` will contain the result for the capacity
    measurement, and cycles will be a list of dictionaries with details of all
    the dis/charge cycles used for this measurement. The ``cycles`` value is
    the result from calling `BatCapHistory.measureSummary` for the matching
    capacity measurement history entry.

    Args:
        bat_id: The battery ID used as `Battery.bat_id` field to find the
            battery entry.
        uid: The capacity measurement UID used as the `BatCapHistory.soc_uid`
            field to find the linked measurement history entry for the battery.
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.

    Returns:
        The result dictionary as mentioned above.
    """

    res = {
        "success": False,
        "msg": "",
        "details": None,
        "cycles": None,
    }

    with db.connection_context():
        # Get the battery
        bat = Battery.get_or_none(Battery.bat_id == bat_id)
        if not bat:
            res["msg"] = f"No battery found with ID {bat_id}."
            return res

        # ... and the history entry for this UID
        uid_hist = bat.cap_history.where(BatCapHistory.soc_uid == uid).get_or_none()
        if not uid_hist:
            res["msg"] = (
                f"No measurement with UID {uid} found for battery with ID {bat_id}."
            )
            return res

        # ... and the measurements summary
        cycles = uid_hist.measureSummary()
        if not cycles:
            res["msg"] = (
                f"No measurement cycles found for UID {uid} for battery with ID {bat_id}."
            )
            return res

        # Build the result
        res["success"] = True
        res["details"] = {
            "bat_id": bat_id,
            "uid": uid,
            "cap_date": (
                uid_hist.cap_date
                if raw_dates
                else uid_hist.cap_date.strftime("%Y-%m-%d %H:%M:%S")
            ),
            "mah": uid_hist.mah,
            "accuracy": uid_hist.accuracy,
            "shunt": {
                "ch": uid_hist.per_dch["ch"]["shunt"],
                "dch": uid_hist.per_dch["dch"]["shunt"],
            },
            "bc_name": cycles[0]["bc_name"],
        }
        res["cycles"] = cycles

        return res


def getBatMeasurementPlotData(bat_id: str, uid: str, plot_ind: str) -> list[dict]:
    """
    Returns a list of measure points for a given measurement cycle that may be
    used to plot on graph.

    The ``bat_id`` and ``uid`` args will be the same as for the
    `getBatMeasurementByUID`. The result returned from that call will also have
    a ``plot_ind`` in the dictionary returned for each of the measurement
    cycles.

    This function will return the measure data for any of these cycles using
    the ``plot_ind`` for the cycle.

    This is the result from `BatCapHistory.plotData` and may look like:

    .. python::

        [
          {'timestamp': 1738461564718.08,
           'bat_v': 4216,
           'current': 221,
           'charge': 9142316,
           'mah': 2540},
          {'timestamp': 1738461631577.57,
           'bat_v': 4216,
           'current': 219,
           'charge': 9157147,
           'mah': 2544},
          {'timestamp': 1738461698531.54,
           'bat_v': 4215,
           'current': 215,
           'charge': 9171582,
           'mah': 2548},
           .
           .
           .
        ]

    Args:
        bat_id: See `getBatMeasurementByUID`
        uid: See `getBatMeasurementByUID`
        plot_ind: The ``plot_ind`` value in any cycle entry as returned by
            `getBatMeasurementByUID`

    Returns:
        As described above.
    """

    res = {
        "success": False,
        "msg": "",
        "cycle": "",
        "cycle_num": 0,
        "plot_data": None,
    }

    with db.connection_context():
        # Get the battery
        bat = Battery.get_or_none(Battery.bat_id == bat_id)
        if not bat:
            res["msg"] = f"No battery found with ID {bat_id}."
            return res

        # ... and the history entry for this UID
        uid_hist = bat.cap_history.where(BatCapHistory.soc_uid == uid).get_or_none()
        if not uid_hist:
            res["msg"] = (
                f"No measurement with UID {uid} found for battery with ID {bat_id}."
            )
            return res

        # ... and the plot data
        cycle, cycle_num, plot_data = uid_hist.plotData(plot_ind)
        if not plot_data:
            res["msg"] = (
                f"No plot data found for UID {uid} for battery with ID {bat_id}."
            )
            return res

        # Build the result
        res["success"] = True
        res["plot_data"] = plot_data
        res["cycle"] = cycle
        res["cycle_num"] = cycle_num

        return res

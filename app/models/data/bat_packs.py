"""
Data interface between API/Web endpoints and the raw data related to battery
packs.

Attributes:
    logger: A logger instance for the local module.
"""

import logging

from typing import Iterable

from peewee import Case, JOIN, fn
from playhouse.shortcuts import model_to_dict

from app.utils import datesToStrings

from ..models import db, Battery, InternalResistance, BatteryImage, BatteryPack

logger = logging.getLogger(__name__)

__all__ = [
    "getPacks",
    "getPack",
    "convertIDs",
    "getAvailable",
    "build",
    "savePack",
]


def getPacks(raw_dates: bool = False, search: str | None = None) -> Iterable[dict]:
    """
    Generator that returns all battery packs from the `BatteryPack` table.

    Args:
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.
        search: If supplied, it must be a string that will be used as a LIKE
            SQL search on the pack name field. Only entries where this search
            match will be returned. May be an empty list.

    Yields:
        `BatteryPack` records.
    """
    with db.connection_context():
        query = BatteryPack.select().order_by(BatteryPack.created)

        # Any search criteria?
        if search:
            query = query.where(BatteryPack.name % f"%{search}%")

        # Return the results, but convert any datetime type elements in the result
        # to date/time strings if raw_dates is false
        for row in query.dicts():
            if raw_dates:
                yield row
            else:
                yield datesToStrings(row)


def getPack(pack_id: int | None = None, raw_dates: bool = False, to_dict=True) -> dict:
    """
    Returns the `BatteryPack` instance given by the ``pack_id`` as a
    dictionary.

    To make it easier to generate a new battery pack, we also allow the
    ``pack_id`` to be null. In this case an empty `BatteryPack` record will be
    returned as a dict that can then be completed on the UI.

    Args:
        pack_id: The id for `BatteryPack` to fetch. If None, then an empty
            `BatteryPack` will be instantiated as a new pack (not saved).
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.
        to_dict: If True (default), a dict representing the `BatteryPack` will
            be returned - with ``raw_dates`` applied if required. If False, the
            standard `BatteryPack` instance will be returned - ``raw_dates``
            does not apply.

    Returns:
        None if ``pack_id`` is supplied (not None), but the ID does not exist.
        Else, either the `BatteryPack` entry if ``to_dict`` is ``False``, or a
        dict version of the `BatteryPack` entry if it is True.
        If ``pack_id`` is None, the returned pack will a new and empty
        `BatteryPack`, but would not have been saved to the DB yet (the ID
        would be None).
    """
    logger.info("Fetching BatteryPack with ID: %s", pack_id)

    with db.connection_context():
        # Generate and empty pack dict?
        if pack_id is None:
            pack = BatteryPack()
        else:
            # The
            pack = BatteryPack.get_or_none(BatteryPack.id == pack_id)
            if pack is None:
                logger.info("No BatteryPack with ID %s exists.", pack_id)
                return None

        if not to_dict:
            return pack

        if raw_dates:
            return datesToStrings(model_to_dict(pack))

        return model_to_dict(pack)


def convertIDs(ids: list, raw_dates: bool = False):
    """
    Converts a list of `Battery` IDs to a list of `Battery` entries -
    effectively fetching the `Battery` entry for each valid ID in the list.

    For convenience the list may also be a list of lists as is used in the
    `BatteryPack.config` dict's ``conn`` field which describes the pack
    connection config. In this case though, the result be flattened list of
    `Battery` entries, and not in the same structure as the input list of list.

    Args:
        ids: A list (or list of lists) of `Battery` IDs for which to fetch the
            `Battery` entries.
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.

    Returns:
        A list of `Battery` entries for all found IDs in the input. Each entry
        will be a dictionary and include all the fields from `Battery`, but
        with one extra field called ``has_img`` which will be True if the
        battery has an image linked.
    """
    # We do not want to do selects per id, so we will do one select limited to
    # all the IDs, then create a lookup dict by ID and finally run through ids
    # and replace the ID with the equivalent battery dict.

    # Short circuit if ids is empty
    if not ids:
        return

    # Since IDS can be a list of lists, we need to fatten it first if so
    if isinstance(ids[0], list):
        id_list = [i for sub in ids for i in sub]
    else:
        id_list = ids

    id_map = {}

    with db.connection_context():
        # Subquery to selects the latest IR per battery which gives one row per
        # IR so that `rn =1` be the most recent IR for a battery
        latest_ir_sq = InternalResistance.select(
            InternalResistance.battery_id,
            InternalResistance.int_res,
            InternalResistance.created,
            fn.ROW_NUMBER()
            .over(
                partition_by=[InternalResistance.battery_id],
                order_by=[InternalResistance.created.desc()],
            )
            .alias("rn"),
        ).alias("latest_ir")

        # All the batteries that do not currently belong to a pack
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
                latest_ir_sq.c.int_res.alias("ir"),
                latest_ir_sq.c.created.alias("ir_created"),
            )
            # Join image table first (one-to-one, so no row multiplication)
            .join(BatteryImage, JOIN.LEFT_OUTER)
            # latest IR (windowed subquery)
            .join(
                latest_ir_sq,
                JOIN.LEFT_OUTER,
                on=(Battery.id == latest_ir_sq.c.battery_id),
            )
            # only keep the "latest" IR row (or none)
            .where(
                (Battery.id << id_list)
                & ((latest_ir_sq.c.rn == 1) | latest_ir_sq.c.rn.is_null())
            )
        )

        # Create the lookup map
        for row in query.dicts():
            id_map[row["id"]] = row if raw_dates else datesToStrings(row)

    def replaceIDs(target):
        """
        Recursive function that will replace all IDs in the flat target list
        with the battery dict from id_map.
        """
        for idx, bat_id in enumerate(target):
            if isinstance(bat_id, list):
                replaceIDs(bat_id)
                continue

            target[idx] = id_map[bat_id]

    # Recursively replace IDs with equivalent battery dicts
    replaceIDs(ids)


def getAvailable(excl: list | None = None, raw_dates: bool = False):
    """
    Returns a list of available batteries that can be used to construct a pack.

    Any battery that does not already belong to a pack is available.

    In addition, while building the pack, we would add batteries temporarily
    until the full pack is completed, and only then update the individual
    `Battery` entries to belong to the final pack. To make sure we do not
    include these temp batteries in the pack, their IDs can be passed as a
    list in the ``excl`` argument.

    The ``excl`` list could either be a flat list of IDs, or it could be a pack
    connection list of lists, i.e. ``[ [id, ...], ...]``

    Args:
        excl: An optional list of battery IDs to exclude from the list of
            available `Battery` entries.
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.

    .. note::
        The ``has_img`` field is a bool to indicate if this battery has an
        image in `BatteryImage`.

        If ``True``, the UI can use whatever URL renders the battery images to
        show the image. This should be something like ``/bat/{bat_id}/img``.

        If ``False``, then no image is available to render.

    Yields:
        `Battery` entries with the additional ``has_img`` field:

        .. python::
            {
              'id': 24,
              'created': '2025-05-03 11:42:57',
              'modified': '2025-05-03 11:42:57',
              'bat_id': '2025050202',
              'cap_date': '2025-05-12',
              'mah': 1393,
              'accuracy': 98,
              'ir': 441,
              'ir_created': '2026-01-01',
              'has_img': True/False,
             }
    """
    # Peewee where clauses has to be written as singleton comparisons so,
    # @pylint: disable=singleton-comparison

    # Flatten the exclude list if needed
    if excl:
        # Is it a list of list as for the pack connections?
        if isinstance(excl[0], list):
            # For every serial string in the parallele list, extract the bat id
            # in to a flat list.
            ex_list = [bid for serial in excl for bid in serial]
        else:
            # We assume it's a flat list of IDs
            ex_list = excl
    else:
        ex_list = None

    with db.connection_context():
        # Subquery to selects the latest IR per battery which gives one row per
        # IR so that `rn =1` be the most recent IR for a battery
        latest_ir_sq = InternalResistance.select(
            InternalResistance.battery_id,
            InternalResistance.int_res,
            InternalResistance.created,
            fn.ROW_NUMBER()
            .over(
                partition_by=[InternalResistance.battery_id],
                order_by=[InternalResistance.created.desc()],
            )
            .alias("rn"),
        ).alias("latest_ir")

        # All the batteries that do not currently belong to a pack
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
                latest_ir_sq.c.int_res.alias("ir"),
                latest_ir_sq.c.created.alias("ir_created"),
            )
            # Join image table first (one-to-one, so no row multiplication)
            .join(BatteryImage, JOIN.LEFT_OUTER)
            # latest IR (windowed subquery)
            .join(
                latest_ir_sq,
                JOIN.LEFT_OUTER,
                on=(Battery.id == latest_ir_sq.c.battery_id),
            )
            # only keep the "latest" IR row (or none)
            .where(
                (Battery.pack.is_null(True))
                & ((latest_ir_sq.c.rn == 1) | latest_ir_sq.c.rn.is_null())
            )
        )

        # Exclude those from the exclude list too
        if ex_list:
            query = query.where(Battery.id.not_in(ex_list))

        # Return the results, but convert any datetime type elements in the result
        # to date/time strings if raw_dates is false
        for row in query.dicts():
            if raw_dates:
                yield row
            else:
                yield datesToStrings(row)


def optimalPack(bats: list, voltage: int, id_only=False):
    """
    Called from `build` after batteries have been validated to ensure we will
    only use available batteries for this pack.

    Build a battery pack to have a nominal voltage of ``voltage`` given a
    list of `Battery` entries to use.

    If not enough batteries are available to make up the nominal voltage, the
    pack will be empty.

    First the serial count (S) is calculated by dividing the required pack
    ``voltage`` by the nominal cells voltage (`BatteryPack.NOM_V`)

    With the S count known, the available batteries will be grouped in
    subgroups of parallel combos. The number of batteries in each of these
    parallel packs will be the P count for pack.

    Either S or P may be 1, depending on the pack voltage and the number of
    batteries available.

    For example, given ``bats`` as a list of 7 `Battery` entries with different
    capacities, and a nominal pack voltage of 10.8 volt required, S will be
    calculated as 3 (3 series connections) and P
    as 2.

    For an optimal pack, we calculate it having to be connected like below, 3S
    of 2P or 3S2P:

    ::

        + ----(+b_3-]--(+b_6-]--(+b_1-]---- -
               |   |    |   |    |   |
              (+b_7-]  (+b_2-]  (+b_4-]

    Since there were 7 batteries, but only 6 can be used, ``b_5`` was the least
    capable and is left over.

    For this configuration, the pack connection config will be returned as
    a list of lists:

    .. python::

        [
            [b_3, b_7],
            [b_6, b_2],
            [b_1, b_4],
        ]

    And the extra left over will be a list of ``[c_5]``.

    Note that the ``config`` value returned will be the same format as for
    `BatteryPack.config`. The only difference may be ``conn`` list of
    `Battery` entries. If ``id_only`` is True, then this list will only contain
    the battery IDs as for the `BatteryPack` default. If is is False, each
    element in the serial string lists in ``conn`` will be the full `Battery`
    entry as a dictionary.

    The second form makes it easy to surface these batteries on a UI where
    richer battery info is needed. For storing connection config, only the
    `Battery.id` is needed.

    Args:
        bats: Query set of `Battery` entries to use for the pack, as passed in
            from `build` for example.
        voltage: Desired pack voltage as a multiple of `BatteryPack.NOM_V`
        id_only: If ``False`` (default), then the elements returned in the
            ``config`` and ``extra`` lists will be full `Battery` entries as
            dictionaries. If True, then only the `Battery.id` values will be
            used in these lists.

    Returns:
        A dictionary:

        .. python::
            {
              'capacity': int              # total pack capacity in mAh (min series string)
              'config': {"struct": "nSnP", "conn": []} # see above
              'extra': [id,...],           # leftover cells
            }
    """
    series_count = int(round(voltage / BatteryPack.NOM_V))

    # If the series count is more than the number of available bat_ids, they
    # all go to extra
    if series_count > len(bats):
        logging.info(
            "Not enough batteries to build a pack with voltage of %sV", voltage
        )
        return {
            "capacity": 0,
            "config": {"struct": "0S0P", "conn": []},
            "extra": bats.dicts().get() if not id_only else [b.id for b in bats],
        }

    # The parallel string count depends on the number batteries available.
    parallel_count = len(bats) // series_count
    # Total batteries in the pack
    pack_tot = parallel_count * series_count  ### 2

    # Sort batteries descending by capacity
    bats = sorted(bats, key=lambda b: b.mah, reverse=True)

    # Slice pack batteries and extras, and convert model entries to dicts
    pack_bats = [model_to_dict(b) for b in bats[:pack_tot]]
    extra_bats = [model_to_dict(b) for b in bats[pack_tot:]]

    # Initialize a bin for each set of parallel strings we will need.
    bins = [{"sum": 0, "items": []} for _ in range(series_count)]

    # Greedy assignment: largest to first parallel bin with smallest sum that
    # has room
    for bat in pack_bats:
        # Find eligible bins (with len < parallel_count)
        eligible = [b for b in bins if len(b["items"]) < parallel_count]
        # Pick the eligible bin with smallest current sum
        target = min(eligible, key=lambda b: b["sum"])
        target["items"].append(bat)
        target["sum"] += bat["mah"]

    # Sort the parallel bins from highest to lowest parallel capacity
    bins.sort(key=lambda c: c["sum"], reverse=True)
    # The pack capacity is that of the lowest parallel string
    pack_cap = bins[-1]["sum"]

    # Convert bins to lists of items
    pack_conn = [b["items"] for b in bins]

    # Need to reduce pack_conn and extra_bats to IDs only if id_only is True
    if id_only:
        pack_conn = [[b["id"] for b in para] for para in pack_conn]
        extra_bats = [b["id"] for b in extra_bats]

    return {
        "capacity": pack_cap,
        "config": {
            "struct": f"{series_count}S{parallel_count}P",
            "conn": pack_conn,
        },
        "extra": extra_bats,
    }


def build(bat_ids: list, voltage: int, id_only: bool = False) -> dict:
    """
    Will try to build an optimal pack given the required pack nominal voltage
    and the list of batteries to use for the pack.

    Some rules:

    * All IDs in ``bat_ids`` must be valid `Battery` entries.
    * The batteries may not already belong to another `BatteryPack`, but it's
        OK if it belongs to this pack

    The ``pack`` value in the return dict is as returned by `optimalPack`.
    Also see `optimalPack` for details on how the pack is configured for
    optimal capacity.

    Args:
        bat_ids: List of `Battery.id` values.
        voltage: Desired pack voltage as a multiple of `BatteryPack.NOM_V`
        id_only: See same arg for `optimalPack`

    Returns:
        A dictionary:

        .. python::
            {
              # This is the same as returned from `optimalPack`
              'capacity': int              # total pack capacity in mAh (min series string)
              'config': {"struct": "nSnP", "conn": []} # see above
              'extra': [id,...],           # leftover cells
              # This added extra to the above
              'invalid': [],  # list of any invalid ids in bat_ids
              'used':    [],  # list of any batteries already in another pack
            }
    """
    # Will hold a list of any invalid IDS found in bat_ids - if any.
    invalid_ids = []
    used_ids = []

    logger.info("Building pack from bat_ids %s @%smV", bat_ids, voltage)
    # Get the batteries for each of the battery ids
    with db.connection_context():
        bats = Battery.filter(Battery.id << bat_ids)

        # Are all battery IDs valid?
        if bats.count() != len(bat_ids):
            invalid_ids = list(set(bat_ids) - set(bat.id for bat in bats))
            logger.error("Ignoring invalid battery ID(s) for pack: %s", invalid_ids)

        # # Make sure none of the batteries belong to other packs already
        # avail_bats = [bat for bat in bats if (bat.pack is None or bat.pack == self)]
        # if len(avail_bats) != len(bats):
        #     used_ids = list(set(b.id for b in bats) - set(b.id for b in avail_bats))
        #     logger.error("Ignoring batteries already used in another pack: %s", used_ids)

        # Generate the optimal pack
        pack = optimalPack(bats, voltage, id_only)

        # Add the invalid and used lists
        pack.update({"invalid": invalid_ids, "used": used_ids})

        return pack


def savePack(
    pack_id: int | None,
    name: str,
    desc: str | None,
    voltage: int,
    capacity: int,
    config: dict,
    notes: str | None = None,
):
    """
    Saves an existing `BatteryPack` (``pack_id`` is not ``None``) or creates a
    new one.

    The ``config`` will contain the `Battery` IDs that belong to the pack. All
    `Battery` entries that already belong to this pack, but not in the list of
    current pack batteries will have their `Battery.pack` FK reset to ``NULL``.
    Any newly added batteries will have their `Battery.pack` FK set to this
    pack ID.

    Args:
        pack_id: The pack ID for an existing pack, or None for a new pack
        name: The pack name. Required.
        desc: An optional further description for the pack.
        voltage: The pack voltage in mV
        capacity: The pack capacity, as calculated from the connection config
            (this should be known and correct as it is not calculated here).
            Required.
        config: The pack config dictionary as defined for `BatteryPack.config`.
            Required.
        notes: Optional notes to add for this pack.

    Returns:

        A dictionary:

        .. python::
        {
            'success': True/False, # Indicates success
            'pack': BattryPack,    # If success==True, else None
            'error': str,          # If success=False an error message, else None
        }

    """
    res = {
        "success": False,
        "pack": None,
        "error": None,
    }
    # Get the current pack, or a new one if pack_id is None
    pack = getPack(pack_id, to_dict=False)

    # If None, then the pack_id is invalid
    if pack is None:
        res["error"] = f"No pack found with id: {pack_id}"
        return res

    # Now we update the fields, but all is done in an atomic transactions so we
    # can revert if anything fails.
    with db.atomic():
        # Update the pack
        pack.name = name
        pack.desc = (desc.strip() if desc else None) or None
        pack.voltage = voltage
        pack.capacity = capacity
        pack.config = config
        pack.notes = (notes.strip() if notes else None) or None
        # Save it
        pack.save()

        # Now we update the battery pack FKs. First get all the Battery entries
        # for this pack. But we need to flatten the connection config ids
        ids = [i for sub in config["conn"] for i in sub]
        # Get this into a set so we can do set arithmetic
        pack_bats = set(Battery.select().where(Battery.id << ids))

        # Now a set of all the Battery entries that already belong to this pack
        in_pack = set(pack.cells)

        # Any Batteries not in the pack anymore must have their .pack FKs reset
        to_set = in_pack - pack_bats
        for b in to_set:
            b.pack = None
            b.save()

        # Now make sure we set the pack Fks to this pack for those in the pack
        for b in pack_bats:
            if b.pack != pack:
                b.pack = pack
                b.save()

    # All good
    res["success"] = True
    res["pack"] = pack
    return res

"""
Data interface between API/Web endpoints and the raw data related to events
data.
"""

from typing import Iterable
from peewee import fn, SQL

from app.utils import datesToStrings

from ..models import db, SoCEvent

__all__ = [
    "getUnallocatedEvents",
    "delDanglingEvents",
    "getBatUnallocSummary",
    "delUnallocBatEvents",
    "delBatUIDEvents",
    "delExtraSoCEvent",
]


def getUnallocatedEvents(raw_dates: bool = False) -> Iterable[dict]:
    """
    Generator that returns a list of all Battery IDs that have `SoCEvent` s
    which have not been allocated as `BatCapHistory` entries yet - entries
    where the `SoCEvent.bat_history` field is ``NULL``.

    Each entry yielded will be a ``dict`` as follows:

    .. python::

        {
            'bat_id': '2025030801',
            'date': '2025-03-08',

            # Or, if raw_dates is True
            # 'date': datetime.date(2025, 3, 8),

            'events': 3607
        }

    Note:
        The ``bat_id`` may be empty if an event was registered before the
        Battery ID was known.

    Args:
        raw_dates: If True, dates will be returned as datetime objects. If
            False (the default) dates will be be returned as "YYYY-MM-DD HH:MM:SS"
            string

    Yields:
        Each entry is a ``dict`` as shown above.
    """
    with db.connection_context():
        query = (
            SoCEvent.select(
                SoCEvent.bat_id,
                fn.DATE(fn.MIN(SoCEvent.created)).alias("date"),
                fn.SUM(1).alias("events"),
            )
            .where(SoCEvent.bat_history == None)  # pylint: disable=singleton-comparison
            .group_by(SoCEvent.bat_id)
            .order_by(SoCEvent.bat_id)
        )

        # We need to convert the datetime objects to date time strings for each
        # entry
        for row in query.dicts():
            if raw_dates:
                yield row
            else:
                yield datesToStrings(row)


def delDanglingEvents() -> dict:
    """
    Deletes all unallocated `SoCEvent` where the `SoCEvent.bat_id` is NULL.

    These are created on the Capacity Meter when a new battery is inserted but
    before a battery ID is set.

    This should be fixed in the Bat Capacity Meter firmware, but for now we can
    clean it up here.

    Returns:
        A dictionary like:

        .. code::

            {
                'success': True/False,
                'msg': Error or success message than can be surfaced.
            }
    """
    res = {"success": False, "msg": ""}
    with db.connection_context():
        try:
            query = SoCEvent.delete().where(
                # We do this for Peewee, so @pylint: disable=singleton-comparison
                SoCEvent.bat_id == None,
                SoCEvent.bat_history == None,
            )
            cnt = query.execute()
        except Exception as exc:
            res["msg"] = f"Error deleting dangling events: {exc}"
        else:
            # All good, update res
            res["success"] = True
            res["msg"] = f"Deleted {cnt} dangling events"

    return res


def getBatUnallocSummary(battery_id: str, raw_dates: bool = False) -> Iterable[dict]:
    """
    Generator that returns a summary of all unallocated events for the given
    battery ID.

    The summary is a list of the different states for each of the cycles in the
    measurement stages, and a counts of the number events in that stage.

    The SQL query is:

    .. code::

        WITH consecutive_events AS (
        SELECT
            id,
            created,
            bat_id,
            state,
            soc_uid,
            soc_state,
            ROW_NUMBER() OVER (PARTITION BY bat_id ORDER BY created)
              - ROW_NUMBER() OVER (PARTITION BY bat_id, state ORDER BY created) AS grp
        FROM
            soc_event
        WHERE
            bat_id = '<battery_id>' AND bat_history is NULL
        )
        SELECT
            MIN(id) AS id_start, -- The id of the first event in the group
            MAX(id) AS id_end, -- The id of the last event in the group
            MIN(created) AS event_time, -- The first occurrence in each group
            bat_id,
            state,
            soc_uid,
            soc_state,
            COUNT(*) AS event_count -- The number of events in each group
        FROM
            consecutive_events
        GROUP BY
            bat_id, state, soc_uid, soc_state, grp
        ORDER BY
            event_time

    The result from this query may look like this::

        +-------+-------+----------------------------+------------+-------------+----------+----------------+-------------+
        | id_st | id_en | event_time                 | bat_id     | state       | soc_uid  | soc_state      | event_count |
        |-------+-------+----------------------------+------------+-------------+----------+----------------+-------------|
        | 34521 | 34523 | 2025-02-04 16:12:44.966774 | 2025020401 | Battery+ID  | <null>   | <null>         | 3           |
        | 34524 | 36841 | 2025-02-04 16:12:48.348954 | 2025020401 | Charging    | e30cfb16 | Initial Charge | 2318        |
        | 36841 | 36842 | 2025-02-04 16:57:24.931618 | 2025020401 | Charged     | e30cfb16 | Resting        | 1           |
        | .     | .     | 2025-02-04 17:02:25.528027 | 2025020401 | Discharging | e30cfb16 | Discharging    | 13827       |
        | .     | .     | 2025-02-04 21:28:29.135872 | 2025020401 | Discharged  | e30cfb16 | Resting        | 1           |
        | .     | .     | 2025-02-04 21:33:06.881902 | 2025020401 | Charging    | e30cfb16 | Charging       | 15623       |
        | .     | .     | 2025-02-05 02:33:35.720401 | 2025020401 | Charged     | e30cfb16 | Resting        | 1           |
        | .     | .     | 2025-02-05 02:38:35.495934 | 2025020401 | Discharging | e30cfb16 | Discharging    | 13781       |
        | .     | .     | 2025-02-05 07:03:43.768603 | 2025020401 | Discharged  | e30cfb16 | Resting        | 1           |
        | .     | .     | 2025-02-05 07:06:44.319853 | 2025020401 | Charging    | e30cfb16 | Charging       | 14055       |
        | .     | .     | 2025-02-05 11:37:05.163452 | 2025020401 | Charged     | e30cfb16 | Completed      | 1           |
        | .     | .     | 2025-02-05 17:12:14.572511 | 2025020401 | Yanked      | <null>   | <null>         | 1           |
        +-------+-------+----------------------------+------------+-------------+----------+----------------+-------------+

    ... and will yield the following list of dicts::

        [
            {
                'id_start': 34521,
                'id_end': 34523,
                'event_time': datetime.datetime(2025, 2, 4, 16, 12, 44, 966774),
                'bat_id': '2025020401',
                'state': 'Battery+ID',
                'soc_uid': None,
                'soc_state': None,
                'event_count': 3,
            }
            .
            .
            .
            # When raw_dates is False (default)
            {
                'id_start': ...,
                'id_end': ...,
                'event_time': "2025-02-05 17:12:14"),
                'bat_id': '2025020401',
                'state': 'Yanked',
                'soc_uid': None,
                'soc_state': None,
                'event_count': 1,
            }
        ]

    Args:
        battery_id: The battery ID to get the events for.
        raw_dates: If True, dates will be returned as datetime objects. If
            False (the default) dates will be be returned as "YYYY-MM-DD HH:MM:SS"
            string

    Yields:
        A dictionary as shown above..
    """  # pylint: disable=line-too-long

    with db.connection_context():
        # Aliases for clarity
        created = SoCEvent.created
        bat_id = SoCEvent.bat_id
        state = SoCEvent.state
        soc_uid = SoCEvent.soc_uid
        soc_state = SoCEvent.soc_state
        bat_history = SoCEvent.bat_history

        # Define window functions
        row_number_bat = fn.ROW_NUMBER().over(partition_by=[bat_id], order_by=[created])

        row_number_bat_state = fn.ROW_NUMBER().over(
            partition_by=[bat_id, state], order_by=[created]
        )

        # Define the CTE (Common Table Expression)
        consecutive_events = (
            SoCEvent.select(
                SoCEvent.id,
                created,
                bat_id,
                state,
                soc_uid,
                soc_state,
                (row_number_bat - row_number_bat_state).alias("grp"),
            )
            .where(
                bat_id == battery_id,
                bat_history == None,  # pylint: disable=singleton-comparison
            )
            .cte("consecutive_events")  # Define the CTE name
        )

        # Main query using the CTE
        query = (
            SoCEvent.select(
                fn.MIN(consecutive_events.c.id).alias("id_start"),
                fn.MAX(consecutive_events.c.id).alias("id_end"),
                fn.MIN(consecutive_events.c.created).alias("event_time"),
                consecutive_events.c.bat_id,
                consecutive_events.c.state,
                consecutive_events.c.soc_uid,
                consecutive_events.c.soc_state,
                fn.COUNT("*").alias("event_count"),
            )
            .from_(consecutive_events)  # Reference the CTE
            .group_by(
                consecutive_events.c.bat_id,
                consecutive_events.c.state,
                consecutive_events.c.soc_uid,
                consecutive_events.c.soc_state,
                consecutive_events.c.grp,
            )
            .order_by(SQL("event_time"))
            .with_cte(consecutive_events)  # Reference the CTE
        )

        # We need to convert the datetime objects to date time strings for each
        # entry if raw_dates is True
        for row in query.dicts():
            if raw_dates:
                yield row
            else:
                yield datesToStrings(row)


def delUnallocBatEvents(bat_id: str) -> dict:
    """
    Deletes all unallocated SoCEvents for a battery.

    An unallocated event is one for which the `SoCEvent.bat_history` is NULL.

    Args:
        bat_id: The Battery ID for which to delete unallocated events.

    Returns:
        A dictionary like:

        .. code::

            {
                'success': True/False,
                'msg': Error or success message than can be surfaced.
            }
    """
    res = {"success": False, "msg": ""}
    with db.connection_context():
        try:
            query = SoCEvent.delete().where(
                SoCEvent.bat_id == bat_id,
                SoCEvent.bat_history == None,  # pylint: disable=singleton-comparison
            )
            cnt = query.execute()
        except Exception as exc:
            res["msg"] = f"Error deleting unallocated events for bat ID {bat_id}: {exc}"
        else:
            # All good, update res
            res["success"] = True
            res["msg"] = f"Deleted {cnt} events for bat ID {bat_id}"

    return res


def delBatUIDEvents(bat_id: str, uid: str) -> dict:
    """
    Deletes all unallocated `SoCEvent` s for a battery and it's related unique
    measurement event IDs (`SoCEvent.soc_uid`).

    An unallocated event is one for which the `SoCEvent.bat_history` is NULL.

    Args:
        bat_id: The Battery ID for which events are to be deleted.
        uid: The `SoCEvent.soc_uid` for which events are to be deleted.

    Returns:
        A dictionary like:

        .. code::

            {
                'success': True/False,
                'msg': Error or success message than can be surfaced.
            }
    """
    res = {"success": False, "msg": ""}
    with db.connection_context():
        try:
            query = SoCEvent.delete().where(
                SoCEvent.bat_id == bat_id,
                SoCEvent.soc_uid == uid,
                SoCEvent.bat_history == None,  # pylint: disable=singleton-comparison
            )
            cnt = query.execute()
        except Exception as exc:
            res["msg"] = (
                "Error deleting unallocated events for "
                f"bat ID {bat_id} and UID {uid}: {exc}"
            )
        else:
            # All good, update res
            res["success"] = True
            res["msg"] = f"Deleted {cnt} events for bat ID {bat_id} and UID {uid}"

    return res


def delExtraSoCEvent(bat_id: str, soc_id: str | int) -> dict:
    """
    Deletes _stray_ "Charging" `SoCEvent` entries.

    See the description for `delExtraEvent` for more details.

    This will delete the given ``soc_id`` for the given ``bat_id``.

    Args:
        bat_id: The battery ID
        soc_id: The `SoCEvent` ID for this battery ID to delete.
    """
    res = {"success": False, "msg": ""}

    # If this is from the page handler, the soc_id may be a string, so we
    # convert it to an integer.
    if isinstance(soc_id, str) and soc_id.isnumeric():
        soc_id = int(soc_id)

    with db.connection_context():
        try:
            query = SoCEvent.delete().where(
                SoCEvent.id == soc_id,
                SoCEvent.bat_id == bat_id,
            )
            cnt = query.execute()
        except Exception as exc:
            res["msg"] = (
                f"Error deleting SoCEvent with ID {soc_id} for bat ID {bat_id}: {exc}"
            )
        else:
            if cnt != 1:
                res["msg"] = (
                    f"No SoCEvent found with ID {soc_id} for bat ID {bat_id} to delete"
                )
            else:
                # All good, update res
                res["success"] = True
                res["msg"] = f"Deleted SoCEvent ID {soc_id} for bat ID {bat_id}"

    return res

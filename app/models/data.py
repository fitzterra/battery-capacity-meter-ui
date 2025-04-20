"""
Data interface between API/Web endpoints and the raw data.
"""

from typing import Iterable
from peewee import fn, SQL

from app.utils import datesToStrings
from .models import db, SoCEvent, Battery, BatCapHistory


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
                fn.DATE(SoCEvent.created).alias("date"),
                fn.SUM(1).alias("events"),
            )
            .where(SoCEvent.bat_history == None)  # pylint: disable=singleton-comparison
            .group_by(SoCEvent.bat_id, SQL("date"))
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


def getBatUnallocSummary(battery_id: str, raw_dates: bool = False) -> Iterable[tuple]:
    """
    Generator that returns a summary of all unallocated events for the given
    battery ID.

    The summary is a list of the different states for each of the cycles in the
    measurement stages, and a counts of the number events in that stage.

    The SQL query is:

    .. code::

        WITH consecutive_events AS (
        SELECT
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

        +----------------------------+------------+-------------+----------+----------------+-------------+
        | event_time                 | bat_id     | state       | soc_uid  | soc_state      | event_count |
        |----------------------------+------------+-------------+----------+----------------+-------------|
        | 2025-02-04 16:12:44.966774 | 2025020401 | Battery+ID  | <null>   | <null>         | 3           |
        | 2025-02-04 16:12:48.348954 | 2025020401 | Charging    | e30cfb16 | Initial Charge | 2318        |
        | 2025-02-04 16:57:24.931618 | 2025020401 | Charged     | e30cfb16 | Resting        | 1           |
        | 2025-02-04 17:02:25.528027 | 2025020401 | Discharging | e30cfb16 | Discharging    | 13827       |
        | 2025-02-04 21:28:29.135872 | 2025020401 | Discharged  | e30cfb16 | Resting        | 1           |
        | 2025-02-04 21:33:06.881902 | 2025020401 | Charging    | e30cfb16 | Charging       | 15623       |
        | 2025-02-05 02:33:35.720401 | 2025020401 | Charged     | e30cfb16 | Resting        | 1           |
        | 2025-02-05 02:38:35.495934 | 2025020401 | Discharging | e30cfb16 | Discharging    | 13781       |
        | 2025-02-05 07:03:43.768603 | 2025020401 | Discharged  | e30cfb16 | Resting        | 1           |
        | 2025-02-05 07:06:44.319853 | 2025020401 | Charging    | e30cfb16 | Charging       | 14055       |
        | 2025-02-05 11:37:05.163452 | 2025020401 | Charged     | e30cfb16 | Completed      | 1           |
        | 2025-02-05 17:12:14.572511 | 2025020401 | Yanked      | <null>   | <null>         | 1           |
        +----------------------------+------------+-------------+----------+----------------+-------------+

    ... and will yield the following list of tuples::

        [(datetime.datetime(2025, 2, 4, 16, 12, 44, 966774), '2025020401', 'Battery+ID', None, None, 3),
         (datetime.datetime(2025, 2, 4, 16, 12, 48, 348954), '2025020401', 'Charging', 'e30cfb16', 'Initial Charge', 2318),
         (datetime.datetime(2025, 2, 4, 16, 57, 24, 931618), '2025020401', 'Charged', 'e30cfb16', 'Resting', 1),
         (datetime.datetime(2025, 2, 4, 17, 2, 25, 528027), '2025020401', 'Discharging', 'e30cfb16', 'Discharging', 13827),
         (datetime.datetime(2025, 2, 4, 21, 28, 29, 135872), '2025020401', 'Discharged', 'e30cfb16', 'Resting', 1),
         (datetime.datetime(2025, 2, 4, 21, 33, 6, 881902), '2025020401', 'Charging', 'e30cfb16', 'Charging', 15623),
         (datetime.datetime(2025, 2, 5, 2, 33, 35, 720401), '2025020401', 'Charged', 'e30cfb16', 'Resting', 1),
         (datetime.datetime(2025, 2, 5, 2, 38, 35, 495934), '2025020401', 'Discharging', 'e30cfb16', 'Discharging', 13781),
         # When raw_dates is False (default)
         ("2025-02-05 07:03:43"), '2025020401', 'Discharged', 'e30cfb16', 'Resting', 1),
         ("2025-02-05 07:06:44"), '2025020401', 'Charging', 'e30cfb16', 'Charging', 14055),
         ("2025-02-05 11:37:05"), '2025020401', 'Charged', 'e30cfb16', 'Completed', 1),
         ("2025-02-05 17:12:14"), '2025020401', 'Yanked', None, None, 1)]

    Args:
        battery_id: The battery ID to get the events for.
        raw_dates: If True, dates will be returned as datetime objects. If
            False (the default) dates will be be returned as "YYYY-MM-DD HH:MM:SS"
            string

    Yields:
        A 6-tuple as mentioned above.
    """  # pylint: disable=line-too-long

    # TODO: Yield dictionaries instead of tuples like the rest of the data
    # functions.

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
        for row in query.tuples():
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


def getKnownBatteries(raw_dates: bool = False) -> Iterable[dict]:
    """
    Generator that returns all known batteries from the `Battery` table.

    Args:
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.

    Yields:
        Each entry as a dictionary representation of a `Battery` entry.
    """
    with db.connection_context():
        query = Battery.select().order_by(Battery.bat_id)

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
        bat = bat.dicts().get()

        # Return the raw entry if raw_dates is True
        if raw_dates:
            return bat

        # Else convert the dates to strings before returning the dict
        return datesToStrings(bat)


def getBatteryHistory(bat_id: str, raw_dates: bool = False) -> Iterable[dict]:
    """
    Generator that returns all capture history events available for a given
    battery ID.

    This is the SQL we execute:

    .. code::

        select
            b.bat_id,
            b.cap_date,
            h.soc_uid,
            b.mah,
            h.accuracy,
            h.num_events
        from battery b
            inner join bat_cap_history h ON h.battery_id = b.id
        where b.bat_id = '<bat_id>'
        order by b.cap_date desc

    which may a result as::

        +------------+------------+----------+------+----------+------------+
        | bat_id     | cap_date   | soc_uid  | mah  | accuracy | num_events |
        |------------+------------+----------+------+----------+------------|
        | 2025030501 | 2025-03-05 | 28dac6f2 | 1838 | 99       | 57062      |
        +------------+------------+----------+------+----------+------------+

    Args:
        raw_dates: If True, dates will be returned as datetime or date objects.
            If False (the default) dates will be be returned as "YYYY-MM-DD
            HH:MM:SS" (datetimes) or "YYYY-MM-DD" (date only) strings.

    Yields:
        dict: Each entry as a dictionary as follows::

            {
                'bat_id': '2025030501',
                'cap_date': "2025-03-05",

                # Or with raw_dates == True
                # 'cap_date': datetime.date(2025, 3, 5),

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
                Battery.cap_date,
                BatCapHistory.soc_uid,
                Battery.mah,
                BatCapHistory.accuracy,
                BatCapHistory.num_events,
            )
            .join(BatCapHistory)
            .where(Battery.bat_id == bat_id)
            # Order descending on capture date so we get the newest first.
            .order_by(Battery.cap_date.desc())
        )

        # Return the results, but convert any datetime type elements in the result
        # to date/time strings if raw_dates is false
        for row in query.dicts():
            if raw_dates:
                yield row
            else:
                yield datesToStrings(row)


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
        plot_data = uid_hist.plotData(plot_ind)
        if not plot_data:
            res["msg"] = (
                f"No plot data found for UID {uid} for battery with ID {bat_id}."
            )
            return res

        # Build the result
        res["success"] = True
        res["plot_data"] = plot_data

        return res

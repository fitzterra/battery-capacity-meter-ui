"""
Module for working with data from the database.
"""

from datetime import datetime, date

from typing import Iterator
from peewee import fn, SQL

from .models import db, SoCEvent


def dateToStringTuple(tup: tuple) -> tuple:
    """
    Converts any datetime elements in the input tuple to date and time strings
    of the format "YYYY-MM-DD HH:MM:SS"

    This is useful for returning query results that needs to be converted to
    JSON on output, for example.

    Args:
        tup: A tuple with any number of fields, of which one or more may be
            datetime type objects.

    Returns:
        A new tuple with the same elements as the input, except for all
        datetime type elements converted to date/time strings.
    """

    def convIfDate(v):
        """
        Converts v to string representation of a datetime or date item, else it
        just returs v.
        """
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(v, date):
            return v.strftime("%Y-%m-%d")

        return v

    return tuple(convIfDate(f) for f in tup)


def getAllBatIDs() -> Iterator[str]:
    """
    Generator that returns a unique list of battery IDs.

    We get a list of distinct battery IDs from the `SoCEvent` where the ID is not
    NULL.

    Yields:
        An ordered list of battery ID strings
    """
    with db.connection_context():
        query = (
            SoCEvent.select(
                SoCEvent.bat_id,
                fn.DATE(SoCEvent.created).alias("date"),
                fn.SUM(1).alias("events"),
            )
            .group_by(SoCEvent.bat_id, SQL("date"))
            .order_by(SoCEvent.bat_id)
        )

        # First yield the headers
        yield (
            "Battery ID",
            "Date",
            "Events",
        )

        # We need to convert the datetime objects to date time strings for each
        # entry
        for row in query.tuples():
            yield dateToStringTuple(row)


def getSoCEvents(battery_id: str) -> Iterator[tuple]:
    """
    Generator that returns a list of all SoC_ events for a given battery ID.

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
            bat_cap
        WHERE
            bat_id = '<battery_id>'
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


    Yields:
        A list of tuples. For the above results, it may look like this::

            [(datetime.datetime(2025, 2, 4, 16, 12, 44, 966774), '2025020401', 'Battery+ID', None, None, 3),
             (datetime.datetime(2025, 2, 4, 16, 12, 48, 348954), '2025020401', 'Charging', 'e30cfb16', 'Initial Charge', 2318),
             (datetime.datetime(2025, 2, 4, 16, 57, 24, 931618), '2025020401', 'Charged', 'e30cfb16', 'Resting', 1),
             (datetime.datetime(2025, 2, 4, 17, 2, 25, 528027), '2025020401', 'Discharging', 'e30cfb16', 'Discharging', 13827),
             (datetime.datetime(2025, 2, 4, 21, 28, 29, 135872), '2025020401', 'Discharged', 'e30cfb16', 'Resting', 1),
             (datetime.datetime(2025, 2, 4, 21, 33, 6, 881902), '2025020401', 'Charging', 'e30cfb16', 'Charging', 15623),
             (datetime.datetime(2025, 2, 5, 2, 33, 35, 720401), '2025020401', 'Charged', 'e30cfb16', 'Resting', 1),
             (datetime.datetime(2025, 2, 5, 2, 38, 35, 495934), '2025020401', 'Discharging', 'e30cfb16', 'Discharging', 13781),
             (datetime.datetime(2025, 2, 5, 7, 3, 43, 768603), '2025020401', 'Discharged', 'e30cfb16', 'Resting', 1),
             (datetime.datetime(2025, 2, 5, 7, 6, 44, 319853), '2025020401', 'Charging', 'e30cfb16', 'Charging', 14055),
             (datetime.datetime(2025, 2, 5, 11, 37, 5, 163452), '2025020401', 'Charged', 'e30cfb16', 'Completed', 1),
             (datetime.datetime(2025, 2, 5, 17, 12, 14, 572511), '2025020401', 'Yanked', None, None, 1)]

    .. _SoC: https://en.wikipedia.org/wiki/State_of_charge
    """  # pylint: disable=line-too-long
    with db.connection_context():
        # Aliases for clarity
        created = SoCEvent.created
        bat_id = SoCEvent.bat_id
        state = SoCEvent.state
        soc_uid = SoCEvent.soc_uid
        soc_state = SoCEvent.soc_state

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
            .where(bat_id == battery_id)
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

        # First yield the headers
        yield (
            "Time",
            "Battery ID",
            "State",
            "SoC UID",
            "SOC State",
            "Events",
        )

        # We need to convert the datetime objects to date time strings for each
        # entry
        for row in query.tuples():
            yield dateToStringTuple(row)


def getSoCMeasures(uid: str) -> Iterator[tuple]:
    """
    Generator that returns the Charge and Discharge SoC_ measures for a specific
    SoC UID.

    This is the SQL we execute:

    .. code::

        select created, bc_name, state, bat_id, bat_v, mah, period,
               soc_state, CONCAT(soc_cycle, '/', soc_cycles) as cycle
        from bat_cap
        where soc_uid = '<uid>'
           and state in ('Charged', 'Discharged') and soc_state is not NULL
        order by id

    which may have a result as::

        +----------------------------+---------+------------+------------+-------+------+--------+-----------+-------+
        | created                    | bc_name | state      | bat_id     | bat_v | mah  | period | soc_state | cycle |
        |----------------------------+---------+------------+------------+-------+------+--------+-----------+-------|
        | 2025-02-04 16:57:24.931618 | BC0     | Charged    | 2025020401 | 4179  | 198  | 2676   | Resting   | 1/2   |
        | 2025-02-04 21:28:29.135872 | BC0     | Discharged | 2025020401 | 2721  | 1888 | 15960  | Resting   | 1/2   |
        | 2025-02-05 02:33:35.720401 | BC0     | Charged    | 2025020401 | 4176  | 2851 | 18024  | Resting   | 2/2   |
        | 2025-02-05 07:03:43.768603 | BC0     | Discharged | 2025020401 | 2745  | 1877 | 15903  | Resting   | 2/2   |
        | 2025-02-05 11:37:05.163452 | BC0     | Charged    | 2025020401 | 4190  | 2579 | 16217  | Completed | 2/2   |
        +----------------------------+---------+------------+------------+-------+------+--------+-----------+-------+

    Returns:
        A list of tuples. For the above it may be::

            [
                (
                    datetime.datetime(2025, 2, 4, 16, 57, 24, 931618),
                    'BC0', 'Charged', '2025020401', 4179, 198, 2676,
                    'Resting', '1/2'
                ),
                (
                    datetime.datetime(2025, 2, 4, 21, 28, 29, 135872),
                    'BC0', 'Discharged', '2025020401', 2721, 1888, 15960,
                    'Resting', '1/2'
                ),
                (
                    datetime.datetime(2025, 2, 5, 2, 33, 35, 720401),
                    'BC0', 'Charged', '2025020401', 4176, 2851, 18024,
                    'Resting', '2/2'
                ),
                (
                    datetime.datetime(2025, 2, 5, 7, 3, 43, 768603),
                    'BC0', 'Discharged', '2025020401', 2745, 1877, 15903,
                    'Resting', '2/2'
                ),
                (
                    datetime.datetime(2025, 2, 5, 11, 37, 5, 163452),
                    'BC0', 'Charged', '2025020401', 4190, 2579, 16217,
                    'Completed', '2/2'
                )
            ]

    .. _SoC: https://en.wikipedia.org/wiki/State_of_charge
    """  # pylint: disable=line-too-long

    with db.connection_context():
        query = (
            SoCEvent.select(
                SoCEvent.created,
                SoCEvent.bc_name,
                SoCEvent.state,
                SoCEvent.bat_id,
                SoCEvent.bat_v,
                SoCEvent.mah,
                SoCEvent.period,
                SoCEvent.soc_state,
                # This is in fact callable, @pylint: disable=not-callable
                fn.CONCAT(SoCEvent.soc_cycle, "/", SoCEvent.soc_cycles).alias("cycle"),
            )
            .where(
                SoCEvent.soc_uid == uid,
                SoCEvent.state.in_(["Charged", "Discharged"]),
                # This has to be '!=' @pylint: disable=singleton-comparison
                SoCEvent.state != None,
            )
            .order_by(SoCEvent.id)
        )

        # First yield the header
        yield (
            "Date/Time",
            "BC",
            "State",
            "Battery ID",
            "Battery V",
            "mAh",
            "Period",
            "SoC State",
            "Cycle",
        )

        # Return the results, but convert any datetime type elements in the result
        # to date/time strings
        for row in query.tuples():
            yield dateToStringTuple(row)


def getSoCAvg(uid: str, single=False) -> list[tuple] | int:
    """
    Returns the Charge and Discharge average mAh for the SoC_ measure with the
    given UID.

    The charge and discharge totals are not always the same since different
    resistors and flows are used to measure each. Ideally these should be the
    same, but until proper adjustment is available in the Battery Capacity
    Meter, we need to live with this.

    This call will return the average for the Charge and Discharge mAh values
    for a given SoC measure UID.

    Optionally, the average of these two average can also be returend as a
    singe average if the ``single`` arg is ``True``.

    This is the query:

    .. code::

        WITH soc_events AS (
            SELECT bat_id, state, mah
            FROM bat_cap
            WHERE soc_uid = '<uid>'
              AND state IN ('Charged', 'Discharged')
            ORDER BY id
            OFFSET 1   -- Remove the initial SoC charge row
        )
        SELECT
            bat_id,
            state,
            ROUND(AVG(mah))::INTEGER AS avg_mah,  -- Convert to integer
            COUNT(*) AS events  -- Count the number of rows making up the average
        FROM
            soc_events
        GROUP BY
            bat_id, state
        ORDER BY
            state

    with a result that may be this::

        +------------+------------+---------+--------+
        | bat_id     | state      | avg_mah | events |
        |------------+------------+---------+--------|
        | 2025020401 | Charged    | 2715    | 2      |
        | 2025020401 | Discharged | 1883    | 2      |
        +------------+------------+---------+--------+

    Returns:
        A list of tuples like this for the above data::

            [
                ('2025020401', 'Charged', 2715, 2),
                ('2025020401', 'Discharged', 1883, 2)
            ]

        If ``single`` is ``True``, the average of the 2 average ``mAh`` values
        will be returned as a single integer

    .. _SoC: https://en.wikipedia.org/wiki/State_of_charge
    """
    with db.connection_context():
        # Aliases for clarity
        bat_id = SoCEvent.bat_id
        soc_uid = SoCEvent.soc_uid
        state = SoCEvent.state
        mah = SoCEvent.mah

        # Define the "soc_events" CTE
        soc_events_cte = (
            SoCEvent.select(bat_id, state, mah)
            .where((soc_uid == uid) & (state.in_(["Charged", "Discharged"])))
            .order_by(SoCEvent.id)
            .offset(1)  # Skip the first row which is the initial Charge event
            .cte("soc_events")
        )

        # Main query using the CTE
        query = (
            SoCEvent.select(
                soc_events_cte.c.bat_id,
                soc_events_cte.c.state,
                fn.ROUND(fn.AVG(soc_events_cte.c.mah)).cast("Integer").alias("avg_mah"),
                # This is in fact callable, @pylint: disable=not-callable
                fn.COUNT("*").alias("events"),
            )
            .from_(soc_events_cte)  # Selecting from CTE and not SoCEvent
            .group_by(soc_events_cte.c.bat_id, soc_events_cte.c.state)
            .order_by(soc_events_cte.c.state)
            .with_cte(soc_events_cte)
        )

        if single:
            if query.count() != 2:
                # If we do not have exactly 2 rows the value will be invalid, so we
                # return None to show that.
                return None
            # The mAh is the 3rd element in each row. Sum them and divide by 2 to
            # return the rounded average as an int.
            return round(sum(e[2] for e in query.tuples()) / 2)

        return list(query.tuples())

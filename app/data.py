"""
Module for working with data from the database.
"""

from sqlmodel import Session, select, func, text, over, Integer
from .database import engine
from .models import BatCap, BatteryIDs


def getAllBatIDs() -> BatteryIDs:
    """
    Gets a unique list of battery IDs.

    We get a list of distinct battery IDs from the `BatCap` where the ID is not
    NULL.

    Returns:
        An ordered list of battery ID strings
    """
    query = (
        select(BatCap.bat_id)
        .distinct()
        # This has to be '!=' @pylint: disable=singleton-comparison
        .where(BatCap.bat_id != None)
        .order_by(BatCap.bat_id)
    )

    with Session(engine) as sess:
        res = sess.exec(query).all()

    return res


def getSoCEvents(battery_id: str, start_date=None, end_date=None):
    """
    Returns a list of all SoC events for a given battery ID.

    The SQL query is:

    ```sql
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
    ```

    The result from this query may look like this:

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


    Returns:
        A list of tuples. For the above results, it may look like this:

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

    """  # pylint: disable=line-too-long
    # Aliases for clarity
    created = BatCap.created
    bat_id = BatCap.bat_id
    state = BatCap.state
    soc_uid = BatCap.soc_uid
    soc_state = BatCap.soc_state

    # Define row numbers for partitioning
    rn1 = over(
        func.row_number(),
        partition_by=bat_id,
        order_by=created,
    )
    rn2 = over(
        func.row_number(),
        partition_by=[bat_id, state],
        order_by=created,
    )

    # Define the "consecutive_events" CTE
    consecutive_events_cte = (
        select(
            created,
            bat_id,
            state,
            soc_uid,
            soc_state,
            (rn1 - rn2).label("grp"),
        )
        .where(bat_id == battery_id)
        # Optional date filter
        .where(created >= start_date if start_date else text("TRUE"))
        .where(created <= end_date if end_date else text("TRUE"))
        .cte("consecutive_events")
    )

    # Main query using the CTE
    query = (
        select(
            func.min(consecutive_events_cte.c.created).label("event_time"),
            consecutive_events_cte.c.bat_id,
            consecutive_events_cte.c.state,
            consecutive_events_cte.c.soc_uid,
            consecutive_events_cte.c.soc_state,
            func.count().label("event_count"),  # pylint: disable=not-callable
        )
        .group_by(
            consecutive_events_cte.c.bat_id,
            consecutive_events_cte.c.state,
            consecutive_events_cte.c.soc_uid,
            consecutive_events_cte.c.soc_state,
            consecutive_events_cte.c.grp,
        )
        .order_by("event_time")
    )

    with Session(engine) as sess:
        res = sess.exec(query).all()

    return res


def getSoCMeasures(uid: str):
    """
    Returns the Charge and Discharge SoC measures for a specific SoC UID.

    This is the SQL we try to get to:

    ```sql
    select created, bc_name, state, bat_id, bat_v, mah, period,
           soc_state, CONCAT(soc_cycle, '/', soc_cycles) as cycle
    from bat_cap
    where soc_uid = '<uid>'
       and state in ('Charged', 'Discharged') and soc_state is not NULL
    order by id
    ```

    which may have a result as :

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
        A list of tuples. For the above it may be:

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



    """  # pylint: disable=line-too-long

    query = (
        select(
            BatCap.created,
            BatCap.bc_name,
            BatCap.state,
            BatCap.bat_id,
            BatCap.bat_v,
            BatCap.mah,
            BatCap.period,
            BatCap.soc_state,
            # This is in fact callable, @pylint: disable=not-callable
            func.concat(BatCap.soc_cycle, "/", BatCap.soc_cycles).label("cycle"),
        )
        .where(
            BatCap.soc_uid == uid,
            BatCap.state.in_(["Charged", "Discharged"]),
            # This has to be '!=' @pylint: disable=singleton-comparison
            BatCap.state != None,
        )
        .order_by(BatCap.id)
    )

    with Session(engine) as sess:
        res = sess.exec(query).all()

    return res


def getSoCAvg(uid: str, single=False) -> list[tuple] | int:
    """
    Returns the Charge and Discharge average mAh for the SoC measure with the
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

    ```sql
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
    ```

    with a result that may be this:

        +------------+------------+---------+--------+
        | bat_id     | state      | avg_mah | events |
        |------------+------------+---------+--------|
        | 2025020401 | Charged    | 2715    | 2      |
        | 2025020401 | Discharged | 1883    | 2      |
        +------------+------------+---------+--------+

    Returns:
        A list of tuples like this for the above data:

            [
                ('2025020401', 'Charged', 2715, 2),
                ('2025020401', 'Discharged', 1883, 2)
            ]

        If ``single`` is ``True``, the average of the 2 average ``mAh`` values
        will be returned as a single integer
    """
    # Aliases for clarity
    bat_id = BatCap.bat_id
    soc_uid = BatCap.soc_uid
    state = BatCap.state
    mah = BatCap.mah

    # Define the "soc_events" CTE
    soc_events_cte = (
        select(bat_id, state, mah)
        .where(soc_uid == uid)
        .where(state.in_(["Charged", "Discharged"]))
        .order_by(BatCap.id)
        .offset(1)  # Skip the first row which is the initial Charge event
        .cte("soc_events")
    )

    # Main query using the CTE
    query = (
        select(
            soc_events_cte.c.bat_id,
            soc_events_cte.c.state,
            func.round(func.avg(soc_events_cte.c.mah)).cast(Integer).label("avg_mah"),
            # This is in fact callable, @pylint: disable=not-callable
            func.count().label("events"),
        )
        .group_by(soc_events_cte.c.bat_id, soc_events_cte.c.state)
        .order_by(soc_events_cte.c.state)
    )

    with Session(engine) as sess:
        res = sess.exec(query).all()

    if single:
        if len(res) != 2:
            # If we do not have exaclty 2 rows the value will be invalid, so we
            # return None to show that.
            return None
        # The mAh is the 3rd element in each row. Sum them and divide by 2 to
        # return the rounded average as an int.
        return round(sum([e[2] for e in res]) / 2)

    return res

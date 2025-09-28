"""
Data interface between API/Web endpoints and the raw data related to event
summary data.
"""

from typing import Iterable

from app.utils import datesToStrings

from ..models import db, SoCEvent

__all__ = [
    "getSummary",
]


def getSummary(
    soc_uid: str, event_count: int = 5, raw_dates: bool = False
) -> Iterable[dict]:
    """
    Generator that returns only a few start, end and transition events for the
    given ``soc_uid``.

    This is a sample of the raw SQL output - some columns were removed, and
    names and values were shortened to make the if fit and only 2 event counts
    are shown, but it should give an idea of the output:

    ::

        | id   | created        | state       | bat_v | current | mah  | period | shunt | soc_state   | cycle | period |
        |------|----------------|-------------|-------|---------|------|--------|-------|-------------|-------|--------|
        | ..21 | ..-17 06:01:06 | Charging    | 3764  | 994     | 0    | 1      | 0.8   | Initial Ch. | 0     | 0      |
        | ..23 | ..-17 06:01:11 | Charging    | 4041  | 971     | 2    | 6      | 0.8   | Initial Ch. | 0     | 5      |
        | ..23 | ..-17 08:14:07 | Charging    | 4229  | 257     | 1453 | 7979   | 0.8   | Initial Ch. | 0     | 7981   |
        | ..26 | ..-17 08:14:12 | Charging    | 4230  | 256     | 1453 | 7984   | 0.8   | Initial Ch. | 0     | 7986   |
        | ..28 | ..-17 08:14:13 | Charged     | 4186  | 3       | 1453 | 7984   | 0.8   | Resting     | 1     | 0      |
        | ..47 | ..-17 08:19:12 | Discharging | 0     | 0       | 0    | 0      | 8.5   | Discharging | 1     | 300    |
        | ..50 | ..-17 08:19:18 | Discharging | 3959  | 458     | 1    | 5      | 8.5   | Discharging | 1     | 5      |
        | ..14 | ..-17 13:17:26 | Discharging | 2604  | 300     | 2013 | 17889  | 8.5   | Discharging | 1     | 17894  |
        | ..17 | ..-17 13:17:30 | Discharged  | 0     | 299     | 2014 | 17892  | 8.5   | Discharging | 1     | 17897  |
        | ..89 | ..-17 13:20:30 | Charging    | 0     | 0       | 0    | 0      | 0.8   | Charging    | 1     | 180    |
        | ..92 | ..-17 13:20:35 | Charging    | 3603  | 1249    | 2    | 5      | 0.8   | Charging    | 1     | 5      |
        | ..95 | ..-17 13:20:40 | Charging    | 3624  | 1220    | 3    | 10     | 0.8   | Charging    | 1     | 9      |
        | ..89 | ..-17 16:21:34 | Charging    | 4233  | 258     | 2199 | 10861  | 0.8   | Charging    | 1     | 10864  |
        | ..92 | ..-17 16:21:39 | Charging    | 4233  | 259     | 2200 | 10866  | 0.8   | Charging    | 1     | 10869  |
        | ..94 | ..-17 16:21:40 | Charged     | 4208  | 3       | 2200 | 10868  | 0.8   | Charging    | 1     | 10871  |
        | ..14 | ..-17 16:26:41 | Discharging | 0     | 0       | 0    | 0      | 8.5   | Discharging | 2     | 300    |
        | ..17 | ..-17 16:26:46 | Discharging | 3965  | 459     | 1    | 5      | 8.5   | Discharging | 2     | 4      |
        | ..54 | ..-17 21:25:37 | Discharging | 2607  | 300     | 2019 | 17932  | 8.5   | Discharging | 2     | 17937  |
        | ..56 | ..-17 21:25:43 | Discharging | 2599  | 299     | 2020 | 17937  | 8.5   | Discharging | 2     | 17942  |
        | ..57 | ..-17 21:25:43 | Discharged  | 0     | 299     | 2020 | 17937  | 8.5   | Discharging | 2     | 17942  |
        | ..94 | ..-17 21:28:45 | Charging    | 3625  | 1285    | 1    | 1      | 0.8   | Charging    | 2     | 1      |
        | ..96 | ..-17 21:28:50 | Charging    | 3647  | 1246    | 2    | 7      | 0.8   | Charging    | 2     | 6      |
        | ..95 | ..-18 00:29:41 | Charging    | 4236  | 268     | 2311 | 10855  | 0.8   | Charging    | 2     | 10858  |
        | ..96 | ..-18 00:29:46 | Charging    | 4234  | 267     | 2312 | 10860  | 0.8   | Charging    | 2     | 10863  |
        | ..97 | ..-18 00:29:47 | Charged     | 4209  | 3       | 2312 | 10860  | 0.8   | Completed   | 2     | 10863  |


    And this is an example of the dictionary yielded for one of the rows above
    (all fields and data are included here):

    .. python::

        {
            'id': 2017694,
            'created': '2025-08-18 00:29:36',
            'state': 'Charging',
            'bat_v': 4235,
            'current': 269,
            'mah': 2311,
            'period': 10850,
            'shunt': 0.8,
            'soc_state': 'Charging',
            'soc_cycle': 2,
            'soc_cycle_period': 10853,
            'soc_uid': 'a683fc1e'
        }

    Args:

        soc_uid: The ``soc_uid`` from the `SoCEvent` table
        event_count: The number events to return for the start, end and
            transition events.
        raw_dates: If True, dates will be returned as datetime objects. If
            False (the default) dates will be be returned as "YYYY-MM-DD HH:MM:SS"
            string

    Yields:
        Each entry is a ``dict`` as shown above.
    """  # pylint: disable=line-too-long

    with db.connection_context():
        # This is a complex query to generate, so we simply run it as a raw
        # query on the SoCEvent table
        # NOTE: Peewee's parameter binding in raw queries can not have named
        # parameters in the query, so it will make this query very cumbersome
        # to generate. For this reason we are using python string interpolation
        # via f-strings here, which does open us up to SQL injection, but this
        # is currently an internal project, so we should be safe....
        query = SoCEvent.raw(
            f"""
            WITH ordered AS (
                 SELECT
                     *,
                     LAG(state) OVER (PARTITION BY soc_uid ORDER BY id) AS prev_state,
                     ROW_NUMBER() OVER (PARTITION BY soc_uid ORDER BY id) AS rn,
                     COUNT(*) OVER (PARTITION BY soc_uid) AS total_rows
                 FROM soc_event
                 WHERE soc_uid = '{soc_uid}'
             ),
             transitions AS (
                 SELECT id, soc_uid, state, prev_state, rn
                 FROM ordered
                 WHERE prev_state IS NOT NULL
                   AND prev_state <> state
             ),
             windows AS (
                 -- rows around transitions (±event_count)
                 SELECT o.*, 'transition_window' AS region_type, t.rn AS transition_rn
                 FROM transitions t
                 JOIN ordered o
                   ON o.soc_uid = t.soc_uid
                  AND o.rn BETWEEN t.rn - {event_count} AND t.rn + {event_count}

                 UNION ALL

                 -- first event_count rows
                 SELECT o.*, 'start' AS region_type, NULL::integer AS transition_rn
                 FROM ordered o
                 WHERE o.rn BETWEEN 1 AND {event_count}

                 UNION ALL

                 -- last event_count rows
                 SELECT o.*, 'end' AS region_type, NULL::integer AS transition_rn
                 FROM ordered o
                 WHERE o.rn BETWEEN o.total_rows - {event_count-1} AND o.total_rows
             )
             SELECT DISTINCT
                 id,
                 created,
                 state,
                 bat_v,
                 current,
                 mah,
                 period,
                 shunt,
                 soc_state,
                 soc_cycle,
                 soc_cycle_period,
                 soc_uid --,
             FROM windows
             ORDER BY id;
            """
        )

        # We need to convert the datetime objects to date time strings for each
        # entry
        for row in query.dicts():
            if raw_dates:
                yield row
            else:
                yield datesToStrings(row)

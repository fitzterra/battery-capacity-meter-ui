"""
Data interface between API/Web endpoints and the raw data related to Battery
Controller calibration data.

Attributes:
    logger: A logger instance for the local module.
"""

import logging

from peewee import fn

from app.utils import datesToStrings

from ..models import db, BatCapHistory

logger = logging.getLogger(__name__)

__all__ = ["bcCalibration", "needsReTesting"]


def bcCalibration(
    curr: bool = True, hist: bool = True, accuracy: bool = True, raw_dates: bool = False
) -> dict:
    """
    Function to return calibration data for all known Battery Controllers.

    We do not store calibration data directly, but it can be retrieved by
    looking at the history entries in `BatCapHistory`.

    Each of these entries contains the shunt values for that measurement,
    as well as the accuracy obtained using those shunts.

    Furthermore, by tracking where shunt values have changed, we can get a
    fair idea of when any calibrations were done, and thus get some idea of
    calibration history.

    This function returns these types of calibration details:

    * Current calibration settings: This is taken from the last history
        entry per BC.
    * Historic calibration settings: This is a history of all previous
        calibration settings we've seen for each BC, and the date on which
        it was seen first.
    * Accuracy per calibration setting: This is a per BC list of all known
        calibration settings for that BC, and an average of the accuracy
        achieved for that calibration.
    * Best calibration per BC. This is a dict with keys per BC from the accuracy
        list. The value per BC is the best calibration as a
        ``(c_shunt, d_shnut)`` tuple and the date the calibration was set from
        the history list. If ``hist==False``, the calibration date value will
        be None.

    Args:
        curr: Flag to indicate if the current calibration settings should
            be generated.
        hist: Flag to indicate if the historic calibration settings should
            be generated.
        accuracy: Flag to indicate if the accuracy per previous calibration
            settings should be generated.
        raw_dates: True to return dates as datetime, False to return them
            as strings.

    Returns:
        A dictionary as follows:

        .. python::
            {
                'curr': [                             # If curr==True
                    {
                        'bc_name': str,
                        'last_date' : datetime or str,
                        `c_shunt`: float                  # Ohm value
                        `d_shunt`: float,                 # Ohm value
                        `accuracy`: int,                  # Percentage
                    },
                    ...
                ],
                'hist': [                            # If hist==True
                    {
                        'bc_name': str,
                        'c_shunt': float,
                        'd_shunt': float,
                        'calib_date': datetime or str,
                    },
                    ...
                ],
                'accuracy': [                        # If accuracy==True
                    {
                        'bc_name': str,
                        'c_shunt': float,
                        'd_shunt': float,
                        'avg_accuracy': int,
                    },
                    ...
                ],
                'best': {                           # If accuracy==True
                    'bc_name': {
                        'calib': ('c_shunt','d_shunt'):
                        'accu': int,                # Average accuracy
                        'date' : None or date,      # None if hist==False
                    },
                    ...
                }
            }

    """
    res = {}

    with db.connection_context():

        # Define repeated JSON expressions
        c_shunt_expr = fn.json_extract_path_text(BatCapHistory.per_dch, "ch", "shunt")
        d_shunt_expr = fn.json_extract_path_text(BatCapHistory.per_dch, "dch", "shunt")

        # Current calibration?
        if curr:
            # Peewee does not seem to support the PG
            #   SELECT DISTINCT ON (column)
            # which means it will be more complex to make sure we get only the
            # distinct BCs for the most recent capture date.
            # For this reason, we will use a raw query.
            query = BatCapHistory.raw(
                """
                SELECT DISTINCT ON (bc_name)
                  bc_name,
                  date_trunc('second', cap_date) AS cap_date_trunc,
                  per_dch->'ch'->>'shunt' AS c_shunt,
                  per_dch->'dch'->>'shunt' AS d_shunt,
                  accuracy
                FROM bat_cap_history
                ORDER BY bc_name, cap_date DESC
            """
            )

            # Add it to res, converting dates if needed
            res["curr"] = [
                bc if raw_dates else datesToStrings(bc) for bc in query.dicts()
            ]

        # Historic calibration?
        if hist:
            # This is the raw SQL:
            #
            #    SELECT
            #      bc_name,
            #      per_dch->'ch'->>'shunt' AS c_shunt,
            #      per_dch->'dch'->>'shunt' AS d_shunt,
            #      date_trunc('second', MIN(cap_date)) AS calib_date
            #    FROM bat_cap_history
            #    GROUP BY
            #      bc_name,
            #      per_dch->'ch'->>'shunt',
            #      per_dch->'dch'->>'shunt'
            #    ORDER BY
            #      bc_name,
            #      calib_date desc;

            query = (
                BatCapHistory.select(
                    BatCapHistory.bc_name,
                    c_shunt_expr.alias("c_shunt"),
                    d_shunt_expr.alias("d_shunt"),
                    fn.date_trunc("second", fn.MIN(BatCapHistory.cap_date)).alias(
                        "calib_date"
                    ),
                )
                .group_by(
                    BatCapHistory.bc_name,
                    c_shunt_expr,
                    d_shunt_expr,
                )
                .order_by(
                    BatCapHistory.bc_name,
                    fn.date_trunc("second", fn.MIN(BatCapHistory.cap_date)).desc(),
                )
            )

            # Add it to res, converting dates if needed
            res["hist"] = [
                bc if raw_dates else datesToStrings(bc) for bc in query.dicts()
            ]

        # Accuracy details?
        if accuracy:
            # This is the raw SQL
            #    SELECT
            #      bc_name,
            #      per_dch->'ch'->>'shunt' AS c_shunt,
            #      per_dch->'dch'->>'shunt' AS d_shunt,
            #      ROUND(AVG(accuracy), 2) AS avg_accuracy
            #    FROM bat_cap_history
            #    GROUP BY
            #      bc_name,
            #      per_dch->'ch'->>'shunt',
            #      per_dch->'dch'->>'shunt'
            #    ORDER BY
            #      bc_name,
            #      avg_accuracy desc;

            query = (
                BatCapHistory.select(
                    BatCapHistory.bc_name,
                    c_shunt_expr.alias("c_shunt"),
                    d_shunt_expr.alias("d_shunt"),
                    fn.ROUND(fn.AVG(BatCapHistory.accuracy)).alias("avg_accuracy"),
                )
                .group_by(BatCapHistory.bc_name, c_shunt_expr, d_shunt_expr)
                .order_by(
                    BatCapHistory.bc_name,
                    fn.ROUND(fn.AVG(BatCapHistory.accuracy), 2).desc(),
                )
            )

            # Add it to res, converting dates if needed
            res["accuracy"] = [
                bc if raw_dates else datesToStrings(bc) for bc in query.dicts()
            ]

            # Find the best calibration per BC
            res["best"] = {}
            # We assume that the sort order of the accuracy values here are by
            # BC name and accuracy descending. With this order we simply grab
            # the first entry per bc, c_shunt and d_shunt as the best accuracy
            # values.
            for accu in res["accuracy"]:
                bc = accu["bc_name"]
                # Add this BC if we have not done so yet
                if bc not in res["best"]:
                    res["best"][bc] = {
                        "calib": (accu["c_shunt"], accu["d_shunt"]),
                        "date": None,
                        "accu": accu["avg_accuracy"],
                    }

            # Now we can go get the calibration dates for the best accuracies
            # if we have the histories
            if hist:
                for hst in res["hist"]:
                    bc = hst["bc_name"]
                    # Set the date if we have this BC
                    if bc in res["best"] and res["best"][bc]["date"] is None:
                        res["best"][bc]["date"] = hst["calib_date"]
    return res


def needsReTesting() -> list[dict]:
    """
    Determines which batteries needs to be retested after BC recalibration.

    The `bcCalibration` call returns the ``best`` calibrations per BC where the
    accuracy was the highest. For each of these best calibration entries, it
    also return the date the calibration for that BC was made.

    By looking at the last measurement made for each battery, and comparing the
    date it was made with the calibration date for BC the measurement was made
    on, we can deduce that if the measurement date is before the calibration
    date, the battery needs to be retested. This is because a better
    calibration was made after the last test.

    Returns:
        A list of battery entries that needs retesting:

        .. python::

            [
                {
                    'bat_id': '2025012601',
                    'bc_name': 'BC0',
                    'cap_date_str': '2025-01-26 13:34:00'
                },
                ...
            ]
    """
    # Get the list of dates each BC was calibrated for `best` accuracy
    bc_acc = bcCalibration(
        curr=False,
        hist=True,
        accuracy=True,
        raw_dates=False,
    )["best"]

    # Get the last measure per battery and BC.
    # Peewee does not seem to support the PG
    #   SELECT DISTINCT ON (column)
    # which means it will be more complex to make sure we get only the
    # distinct BCs for the most recent capture date.
    # For this reason, we will use a raw query.
    # NOTE: We also convert the cap_date to a string because it will make it
    # easier to compare against the BC calibaration dates which we currently
    # expect to come in as strings.
    query = BatCapHistory.raw(
        """
        SELECT *
        FROM (
            SELECT DISTINCT ON (h.battery_id)
                b.bat_id,
                h.bc_name,
                to_char(h.cap_date, 'YYYY-MM-DD HH24:MI:SS') as cap_date_str
            FROM bat_cap_history h
                inner join battery b on b.id = h.battery_id
            ORDER BY
                h.battery_id, h.cap_date DESC
            ) AS last_test_by_date
        ORDER BY bat_id ASC
    """
    )

    with db.connection_context():
        # Now we go over each last capture entry, check the capture date against
        # the calibration date for that BC. If the BC calibration date is after the
        # capture date, the Battery probably needs retesting
        retest = [
            bat
            for bat in query.dicts()
            if bat["cap_date_str"] < bc_acc[bat["bc_name"]]["date"]
        ]

    return retest

"""
Data interface between API/Web endpoints and the raw data related to Battery
Controller calibration data.

Attributes:
    logger: A logger instance for the local module.
"""

import logging

from peewee import fn

from app.utils import datesToStrings

from ..models import db, BatCapHistory, Battery

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
            query = BatCapHistory.raw(
                """
                WITH shunt_data AS (
                  SELECT
                    bc_name,
                    per_dch->'ch'->>'shunt' AS c_shunt,
                    per_dch->'dch'->>'shunt' AS d_shunt,
                    date_trunc('second', cap_date) AS calib_date,
                    LAG(per_dch->'ch'->>'shunt') OVER (PARTITION BY bc_name ORDER BY cap_date) AS prev_c_shunt,
                    LAG(per_dch->'dch'->>'shunt') OVER (PARTITION BY bc_name ORDER BY cap_date) AS prev_d_shunt
                  FROM bat_cap_history
                )
                SELECT
                  bc_name,
                  c_shunt,
                  d_shunt,
                  calib_date
                FROM shunt_data
                WHERE
                  c_shunt IS DISTINCT FROM prev_c_shunt
                  OR d_shunt IS DISTINCT FROM prev_d_shunt
                ORDER BY
                  bc_name,
                  calib_date DESC
            """
            )
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


def needsReTesting(raw_dates: bool = False) -> list[dict]:
    """
    Determines which batteries needs to be retested after BC recalibration.

    The `bcCalibration` call returns the ``best`` calibrations per BC where the
    accuracy was the highest.

    This functions takes this best accuracy list and looks for any history
    entries where the battery was NOT tested on any BC with it's most accurate
    calibration.

    Args:
        raw_dates: True to return dates as datetime, False to return them
            as strings.

    Returns:
        A list of battery entries that needs retesting:

        .. python::

            [
                {
                    'bat_id': '2025012601',
                    'cap_date': '2025-01-26 13:34:00' or datetime
                },
                ...
            ]
    """
    # Define JSON expressions to grap the shunts from the `per_dch` JSON struct
    c_shunt_expr = fn.json_extract_path_text(BatCapHistory.per_dch, "ch", "shunt")
    d_shunt_expr = fn.json_extract_path_text(BatCapHistory.per_dch, "dch", "shunt")

    # Get the list of best accuracy BC calibrations
    bc_acc = bcCalibration(
        curr=False,
        hist=True,
        accuracy=True,
        raw_dates=False,
    )["best"]

    with db.connection_context():

        # Get all batteries measured with any best calibration
        good_ids = set()
        for bc, dat in bc_acc.items():
            c_shunt, d_shunt = dat["calib"]
            q = (
                BatCapHistory.select(BatCapHistory.battery)
                .where(
                    (BatCapHistory.bc_name == bc)
                    & (c_shunt_expr == c_shunt)
                    & (d_shunt_expr == d_shunt)
                )
                .distinct()
            )
            good_ids.update(b.battery_id for b in q)

        # Get all Batteries that have not bee measured with a best calibrated
        # BC and needs retesting
        query = Battery.select(Battery.bat_id, Battery.cap_date).where(
            Battery.id.not_in(good_ids)
        )

        # Convert to list and dates to strings if needed
        retest = [bat if raw_dates else datesToStrings(bat) for bat in query.dicts()]

    return retest

"""
Data interface between API/Web endpoints and the raw data related to Logs.
"""

from math import ceil
from datetime import datetime

from app.utils import datesToStrings
from app.config import LOG_PAGE_LEN
from ..models import db, Log

__all__ = ["getLogs", "delLogs"]


def getLogs(page: int = 1) -> dict:
    """
    Returns logs for the given page.

    This function will retrieve `LOG_PAGE_LEN` logs or less starting at
    ``OFFSET = (page-1) * LOG_PAGE_LEN``

    Args:
        page: The page of log entries on length `LOG_PAGE_LEN` to return.

    Returns:
        The following dictionary:

        .. python::

            {
                "logs": A list of tuples as (date, msg)
                "page": The current page number,
                "pages": Total pages available at the current `LOG_PAGE_LEN`
            }
    """
    res = {
        "logs": [],
        "page": page,
        "pages": 0,
    }

    with db.connection_context():
        query = (
            Log.select(Log.created, Log.msg)
            .limit(LOG_PAGE_LEN)  # pylint: disable=singleton-comparison
            .offset((page - 1) * LOG_PAGE_LEN)
            .order_by(Log.created)
        )

        res["logs"] = [datesToStrings(row) for row in query.tuples()]

        # Get the total rows
        res["pages"] = ceil(Log.select().count() / LOG_PAGE_LEN)

    return res


def delLogs(before_date: datetime) -> dict:
    """
    Deletes old logs before the given date.

    Args:
        before_date: A ``datetime`` object representing the date before which
            records should be deleted.

    Returns:
        A dictionary as follows:

        .. python::

            {
                "success": False if error, True otherwise,
                "msg": Empty string on success, error message otherwise,
                "deleted": number of records deleted on success.
            }

    """

    res = {"success": False, "msg": "", "deleted": 0}

    try:
        # Start a transaction
        with db.atomic():
            # Get the number of records that will be deleted
            res["deleted"] = Log.delete().where(Log.created < before_date).execute()
            res["success"] = True

    except Exception as e:
        # Handle any errors that occur
        res["msg"] = f"Error occurred: {str(e)}"

    return res

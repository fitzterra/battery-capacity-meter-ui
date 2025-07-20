"""
Data interface between API/Web endpoints and the raw data related to BCM Status
view.

Attributes:
    ACTIVE_AGE: The max age of a `SoCEvent` entry (`SoCEvent.created` field) to
        have it be considered a currently *active* event. Any events older than
        this many seconds are considered to be *inactive*.
"""

from datetime import datetime, timedelta

from app.utils import datesToStrings
from ..models import db, SoCEvent

# See docstring
ACTIVE_AGE = 10

__all__ = [
    "getState",
]


def getState() -> dict:
    """
    Returns the last events per BC from `SoCEvent`, split into *active* and
    *inactive* states.

    This is the effective query we execute:

        SELECT DISTINCT ON (bc_name) *
        FROM soc_event
        ORDER BY bc_name, id DESC;

    Note:
        It is crucial to have an index on the `SoCEvent.bc_name` and
        `SoCEvent.id` (`SoCEvent.id` sorted descending) or else a table scan
        will be done.
        The `SoCEvent` model does not directly define this index because Peewee
        currently does not have support for the descending order on ID.

        It is however set up in the ``indexManager`` in the deployment framework,
        and will be created automatically on deployment if it does not already
        exist.

    Returns:
        The following dictionary:

        .. python::

            {
                "active": The last `SoCEvent` entries per BC that are *younger*
                    than `ACTIVE_BREAK` seconds.
                "active": The last `SoCEvent` entries per BC that are *older*
                    than `ACTIVE_BREAK` seconds.
            }
    """
    res = {
        "active": [],
        "inactive": [],
    }

    with db.connection_context():
        query = (
            SoCEvent.select()
            .distinct(SoCEvent.bc_name)
            .order_by(SoCEvent.bc_name, SoCEvent.id.desc())
        )

        max_active_age = datetime.now() - timedelta(seconds=ACTIVE_AGE)

        for row in query.dicts():
            if row["created"] >= max_active_age:
                res["active"].append(datesToStrings(row))
            else:
                res["inactive"].append(datesToStrings(row))
    return res

"""
This is the main SoC API endpoints
"""

import logging
from microdot.asgi import Microdot

from app.models import data

logger = logging.getLogger(__name__)

app = Microdot()


@app.get("/battery_ids")
async def batteryIDs(_):
    """
    Returns a list of all knows Battery IDs.
    """
    return list(data.getAllBatIDs())


@app.get("/soc_events/<string:bat_id>")
async def socEvents(_, bat_id):
    """
    Returns a list of SoC Events for a given battery ID.
    """
    return list(data.getSoCEvents(bat_id))


@app.get("/soc_measures/<string:uid>")
async def socMeasures(_, uid):
    """
    Returns a list of all SoC Measure events for a given SoC UID
    """
    return list(data.getSoCMeasures(uid))


@app.get("/soc_avg/<string:uid>")
async def socqAvg(request, uid):
    """
    Returns the average SoC by UID....

    ToDo: Fix the docs....
    """

    print(f"Args: {request.args}, {'single' in request.args}")
    if "single" in request.args:
        return {"mAh_avg": data.getSoCAvg(uid, single=True)}

    return list(data.getSoCAvg(uid))

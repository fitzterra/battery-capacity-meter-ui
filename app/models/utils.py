"""
Utility functions focused on direct model and record interaction and
manipulation.
"""

import logging

from .models import (
    db,
    Battery,
    BatCapHistory,
    SoCEvent,
    DatabaseError,
)

# Set up a local logger
logger = logging.getLogger(__name__)


def _validateSoCEvents(events: "ModelSelect", soc_uid: str, bat_id: str) -> dict:
    """
    Validates the `SoCEvent` entries for a valid capacity measurement cycle
    defined by a specific `SoCEvent.soc_uid`

    While validating, it is also calculating stats and info for the measurement
    cycle which will be returned on success.

    Args:
        events: The events selected from the `SoCEvent` table for this
            ``soc_uid``. There is guaranteed to be more than one entry.
        soc_uid: The `SoCEvent.soc_uid` used for the measurement cycle. Mostly
            used for logging.
        bat_id: This is the `SoCEvent.bat_id` determined for the battery from
            the first event entry. Mostly used for logging.

    Returns:
        A dictionary as follows:

        .. python::

            {
                'success': bool,  # Indicates validation success or failure
                'msg': str,       # Error message if validation fails
                'mah_avg':  int,  # The calculated capacity average in mAh
                'accuracy': int,  # A percentage value indicating the accuracy
                                  # between charge and discharge mAh
                                  # measurements. See `BatCapHistory.accuracy`
                                  # for more details.
                'cycles': int,    # The number of cycles used for the capacity
                                  # measurement
                'per_dch': {      # Values specific to the dis/charge cycles
                    'ch': {       # Charge specific values
                        'mah_avg': int,   # Avg mAh for all charge cycles
                        'period': int,    # Avg period in secs for charge cycles
                        'shunt': float    # Shunt resistor in charge circuit
                    },
                    'dch': {
                        'mah_avg': int,   # Avg mAh for all discharge cycles
                        'period': int,    # Avg period in secs for discharge cycles
                        'shunt': float    # Shunt resistor in discharge circuit
                    }
                }
            }

        Only ``msg`` is accurate if ``success == False``.
    """
    # Set up the structure we will return, presetting it as failed.
    res = {
        "success": False,
        "msg": "",
        "mah_avg": 0,
        "accuracy": 0,
        "cycles": 0,
        "per_dch": {
            "ch": {
                "mah_avg": 0,
                "period": 0,
                "shunt": 0,
            },
            "dch": {
                "mah_avg": 0,
                "period": 0,
                "shunt": 0,
            },
        },
    }
    # Get an idea of the number events we are dealing with
    num_events = events.count()

    # All bat_history IDs must be Null, i.e. not linked to a history
    # entry already.
    num_linked = events.where(SoCEvent.bat_history.is_null(False)).count()
    if num_linked == num_events:
        res["msg"] = (
            f"All events for soc_uid {soc_uid} are already marked as "
            f"capacity entries for Battery with ID {bat_id}"
        )
        logger.error(res["msg"])
        return res
    if num_linked != 0:
        res["msg"] = (
            f"Found {num_linked} out of {num_events} SoC Events for "
            f"soc_uid {soc_uid} already linked to history entries. "
            "Unable to complete the capacity setting for this soc_uid"
        )
        logger.error(res["msg"])
        return res

    # The capacity measurement is done by first charging the battery, then
    # one or more discharge/charge cycles. This means that if we look for
    # only events where state is one of 'Charged' or 'Discharged', ordered
    # by id ascending, and we ignore the first one (initial charge), we
    # should be left with at least 2 events, alternating between
    # charged/discharged.
    # These are the event states we are interested in, in the order they
    # should appear in the cycles
    end_states = ["Charged", "Discharged"]

    # Get all end dis/charge events
    end_events = events.where(SoCEvent.state.in_(end_states)).order_by(SoCEvent.id)
    if end_events.count() == 0:
        res["msg"] = (
            f"No end of dis/charge SoC events found for soc_uid {soc_uid}. "
            "Can not determine a capacity entry from this UID."
        )
        logger.error(res["msg"])
        return res

    # Now we cycle through end events, validating each, and also
    # calculating the values we need.

    # The state_idx is an index into end_states we will use to check the
    # pattern of end events follow the expected charge/discharge pattern.
    state_idx = 0

    idx = 0  # Predefine it here so we are sure we can use it after the loop
    for idx, event in enumerate(end_events):
        # Check that we are have the expected event state
        if event.state != end_states[state_idx]:
            res["msg"] = (
                f"End dis/charge SoC event {idx} is state {event.state} while "
                f"it was expected to be in state {end_states[state_idx]} for "
                f"soc_uid {soc_uid}. The measurement events are not in the "
                "expected order."
            )
            logger.error(res["msg"])
            return res
        # Advance the state index to the next state
        state_idx = 0 if state_idx else 1

        # We ignore the initial charge event
        if idx == 0:
            continue

        # Accumulate for the correct charge
        # TODO: Should probably validate that these are valid ints
        res["per_dch"]["ch" if event.state == "Charged" else "dch"][
            "mah_avg"
        ] += event.mah
        res["per_dch"]["ch" if event.state == "Charged" else "dch"][
            "period"
        ] += event.period
        # Record the shunt values
        res["per_dch"]["ch" if event.state == "Charged" else "dch"][
            "shunt"
        ] = event.shunt

    # When we get here, idx starting from 0, should the total number of end
    # events (we exclude the 0th event which is the initial charge event).
    # We require these events to be an even value >= 2
    if idx < 2 or idx % 2 != 0:
        res["msg"] = (
            "Expected to have an odd number (> 3) completed dis/charge "
            f"events but seeing {idx+1} such events. This seems to be a "
            "malformed capacity measurement."
        )
        logger.error(res["msg"])
        return res

    # All looking good. Calculate the final averages
    for avg in res["per_dch"].values():
        # The accumulated values per dis/charge average needs to be divided
        # by the number of the such events, which would be half of idx (idx
        # starts from 0 and we disregard the first charge event, so its
        # value will be the remaining dis/charge events).
        avg["mah_avg"] = avg["mah_avg"] / (idx // 2)
        res["mah_avg"] += avg["mah_avg"]
        avg["period"] = avg["period"] / (idx // 2)

    # The final average needs to be calculated as half of the sum of the two
    # dis/charge averages we accumulated above.
    res["mah_avg"] = round(res["mah_avg"] / 2)

    # The accuracy of the mAh average is calculated as the percentage of the
    # difference between the dis/charge mAh averages, subtracted from the final
    # average, to the final average:
    #
    #            mah_avg - abs(dch_mha_avg - ch_ha_avg)
    # accuracy = --------------------------------------  X 100
    #                          mah_avg
    per_dch = res["per_dch"]
    res["accuracy"] = round(
        (res["mah_avg"] - abs(per_dch["dch"]["mah_avg"] - per_dch["ch"]["mah_avg"]))
        * 100
        // res["mah_avg"]
    )

    res["success"] = True
    return res


def setCapacityFromSocUID(soc_uid: str) -> dict:
    """
    Record a series of `SoCEvent` as a `Battery` capacity measurement.

    See `BatCapHistory` for more details on how battery capacity measurements
    are done through a series of `SoCEvent` received during the measurements
    cycles.

    This function will examine the set of `SoCEvent` s with the given
    ``soc_uid`` for the end of charge and discharge events, and from there
    determine the capacity for the battery for that measurement cycle.

    Once it is able to determine the capacity, it will create a new `Battery`
    entry if one does not already exists, and then create a new `BatCapHistory`
    entry linked to the battery, and lastly link all the `SoCEvent` entries to
    the new `BatCapHistory` entry.

    This function will log any errors and return a dictionary with details on
    success or error with UI surfaceable error/success messages.

    Args:
        soc_uid: The UID used by the Battery Capacity Meter for this
            measurement cycle.

    Returns:
        A dict as follows:

        .. python::

            {
                'success': bool,  # Indicates success of failure
                'msg': str        # An error message explaining the success value
            }
    """
    # Preset the return dict to failure
    res = {"success": False, "msg": "Unknown error."}

    # Select all entries for this soc_uid
    events = SoCEvent.select().where(SoCEvent.soc_uid == soc_uid)
    num_events = events.count()
    if not num_events:
        res["msg"] = f"No SoC Events found with soc_uid {soc_uid}."
        logger.error(res["msg"])
        return res

    # Get the battery id and capacity test date
    # There are peewee dynamic values, so @pylint: disable=unsubscriptable-object
    bat_id = events[0].bat_id
    cap_date = events[0].created
    # pylint: enable=unsubscriptable-object

    logger.info(
        "Found %s events for soc_uid %s and bat_id %s.",
        num_events,
        soc_uid,
        bat_id,
    )

    ### Validation ###

    # Return the validation state for the events, and return with failure is the
    # return state is not True. In this case it will be an error string to be
    # returned to our caller.
    v_res = _validateSoCEvents(events, soc_uid, bat_id)
    if not v_res["success"]:
        res["msg"] = v_res["msg"]
        return res

    ### Capacity Entries Creation ###

    # Now we have everything we need to create the history and battery
    # entry if needed. But we do this in a transaction to ensure we either
    # get everything done, or nothing.
    try:
        with db.atomic():

            # Get the Battery entry for this battery, or create it with our
            # calculated values if it does not exist
            bat, created = Battery.get_or_create(
                bat_id=bat_id, defaults={"mah": v_res["mah_avg"], "cap_date": cap_date}
            )
            if not created and cap_date >= bat.cap_date:
                # This one exists, and the new capture date is greater than
                # the last capture date, so let's update to the new values
                bat.mah = v_res["mah_avg"]
                bat.cap_date = cap_date
                bat.save()

            # Now we can create a new history entry
            bat_cap_hist = BatCapHistory.create(
                battery=bat,
                soc_uid=soc_uid,
                mah=v_res["mah_avg"],
                accuracy=v_res["accuracy"],
                num_events=num_events,
                per_dch=v_res["per_dch"],
            )

            # And lastly, we update all the event entries for this soc_uid to
            # point to the bat_cap_hist instance
            SoCEvent.update(bat_history=bat_cap_hist).where(
                SoCEvent.soc_uid == soc_uid
            ).execute()
    except DatabaseError as exc:
        logger.error(
            "Error setting soc_ui %s as a capacity entry. Error: %s", soc_uid, exc
        )
        res["msg"] = (
            "An error occurred setting this UID as a capacity "
            "entry. See the log for more info"
        )
        return res

    res["success"] = True
    res["msg"] = (
        f"New capacity measure added for Battery with ID '{bat_id}' "
        f"from SoC UID '{soc_uid}'"
    )

    return res

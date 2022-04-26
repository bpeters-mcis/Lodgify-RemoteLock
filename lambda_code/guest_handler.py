from datetime import datetime, timedelta
from lock import Lock
from lodgify import Lodgify
import logging
import json

##############
# Configuration
##############
logging.basicConfig(format='%(levelname)s:  %(message)s', level=logging.INFO)
LIVE = False
with open("config.json") as config_file:
    CONFIG = json.loads(config_file)


def lambda_handler(event, context):

    # Get start and end dates to search
    start_date = datetime.now().strftime("%m-%d-%Y")
    end_date = (datetime.now() + timedelta(days=CONFIG['days_to_check'])).strftime("%m-%d-%Y")

    # Set up objects
    Lodge = Lodgify(config=CONFIG)
    locks = Lock(config=CONFIG)

    # Get all bookings from Lodgify, for the specified date range
    logging.info("================")
    logging.info("Getting Bookings from Lodgify: {} - {}".format(start_date, end_date))
    logging.info("================")
    logging.info("")
    bookings = Lodge.get_bookings(start_date=start_date, end_date=end_date)

    # Go through each booking we have, during the specified window
    logging.info("")
    logging.info("================")
    logging.info("Checking Each Lodgify Booking")
    logging.info("================")
    logging.info("")
    for entry in bookings:
        booking = Lodge.get_booking_details(booking_id=entry)
        logging.info("{}, Guest: {}".format(CONFIG['listings'][booking['property_id']]['display_name'],
                                            booking['guest']['name']))

        # Skip any that are not "booked" status, they wouldn't need a door code yet
        if booking['status'] != "Booked":
            logging.info("-- No action, reservation not booked (no payment yet?)")
            continue

        # Check to see if we've previously sent a door code message to this user
        code_sent = False
        for message in booking['messages']:
            if "code to unlock the door" in message['message']:
                logging.info("--- Code already sent!")
                code_sent = True
                break

        # Create and send a door code if not already done
        if not code_sent:
            logging.info("--- Must create and send a new code.")
            pin = locks.create_pin()

            if LIVE:

                # Create the guest and PIN
                locks.create_new_guest(name=booking['guest']['name'],
                                       email=booking['guest']['email'],
                                       start=booking['arrival'],
                                       end=booking['departure'],
                                       device_id=CONFIG['listings'][booking['property_id']]['lock_device_id'])

                # Send the renter the message with the door code
                Lodge.send_email_message(subject="Your door code for {}".format(CONFIG['listings'][booking['property_id']]['display_name']),
                                         message="The code to unlock the door is: {}".format(pin),
                                         recipient=Lodge.get_booking_email(booking_id=entry))

                logging.info("----- Created code ({}) for user, effective {} - {}".format(pin,
                                                                                          booking['arrival'],
                                                                                          booking['departure']))
            else:
                logging.info("----- TESTING MODE: Would create and message code to this user.")










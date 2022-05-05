from datetime import datetime, timedelta
import requests
import boto3
from lock import Lock
from lodgify import Lodgify
import os
import logging
from config import CODE_EMAIL_TEMPLATE, RENTAL_CONFIGURATION, DAYS_IN_FUTURE_TO_CHECK, LISTING_MAPPING, AWS_CONFIGURATION, EMAIL_CONFIGURATION

##############
# Configuration
##############
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(format='%(levelname)s:  %(message)s', level=logging.INFO)
LIVE = True

def report_errors(errors):
    client = boto3.client('ses', region_name=AWS_CONFIGURATION['region'])
    res = client.send_email(
        Source=EMAIL_CONFIGURATION['from_address'],
        Destination={
            "ToAddresses": [EMAIL_CONFIGURATION['error_reporting_destination']],
            "BccAddresses": EMAIL_CONFIGURATION['bcc_addresses']
        },
        Message={
            'Body': {
                'Html': {
                    'Charset': 'UTF-8',
                    'Data': "<br>".join(errors),
                },
                'Text': {
                    'Charset': 'UTF-8',
                    'Data': ",".join(errors),
                },
            },
            'Subject': {
                'Charset': 'UTF-8',
                'Data': "Errors with Lodgify/Lock Automation Script!",
            },
        }
    )


def send_slack_output(results, errors):
    message = {
        "text": "The Lock Automation Has Run!",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Oscoda Lock Automation Results For {}\n=================================\nTrying to generate codes for rentals up to {} days from now.\n".format(datetime.now(), DAYS_IN_FUTURE_TO_CHECK)
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Codes Sent*\n-----------------\n{}".format("".join(results['codes_sent']))
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Errors*\n-----------------\n{}".format("".join(errors))
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Codes Skipped*\n-----------------\n{}".format("".join(results['codes_skipped']))
                }
            },
        ]
    }

    headers = {
        "Accept": "application/json",
        "Content-type": "application/json"
    }
    response = requests.post(os.getenv("SLACK_WEBHOOK"), headers=headers, json=message)


def lambda_handler(event, context):
    results = {
        "codes_sent": [],
        "codes_skipped": []
    }
    errors = []

    # Get start and end dates to search
    start_date = datetime.now().strftime("%m-%d-%Y")
    end_date = (datetime.now() + timedelta(days=DAYS_IN_FUTURE_TO_CHECK)).strftime("%m-%d-%Y")

    # Set up objects
    Lodge = Lodgify()
    locks = Lock()

    # Get all bookings from Lodgify, for the specified date range
    logging.info("================")
    logging.info("Getting Bookings from Lodgify: {} - {}".format(start_date, end_date))
    logging.info("================")
    logging.info("")
    bookings = Lodge.get_bookings(start_date=start_date, end_date=end_date)

    if not isinstance(bookings, list):
        errors.append(bookings)
        report_errors(errors)
        return

    # Go through each booking we have, during the specified window
    logging.info("")
    logging.info("================")
    logging.info("Checking Each Lodgify Booking")
    logging.info("================")
    logging.info("")
    for entry in bookings:
        booking = Lodge.get_booking_details(booking_id=entry)

        if "ERROR:" in booking:
            errors.append(booking)
            continue

        logging.info("{}, Guest: {}".format(LISTING_MAPPING[booking['property_id']]['display_name'],
                                            booking['guest']['name']))

        # Skip any that are not "booked" status, they wouldn't need a door code yet
        if booking['status'] != "Booked":
            logging.info("-- No action, reservation not booked (no payment yet?)")
            results['codes_skipped'].append("*Property:* {}, *Guest:* {} {}-{} (No yet paid?)\n".format(LISTING_MAPPING[booking['property_id']]['display_name'],
                                                                                                        booking['guest']['name'], booking['arrival'], booking['departure']))
            continue

        # Check to see if we've previously sent a door code message to this user
        code_sent = False
        for message in booking['messages']:
            if CODE_EMAIL_TEMPLATE[3:25] in message['message']:
                logging.info("--- Code already sent!")
                code_sent = True
                results['codes_skipped'].append("*Property:* {}, *Guest:* {} {}-{} (Already sent)\n".format(LISTING_MAPPING[booking['property_id']]['display_name'],
                                                                       booking['guest']['name'], booking['arrival'], booking['departure']))
                break

        # Create and send a door code if not already done
        if not code_sent:
            logging.info("--- Must create and send a new code.")
            pin = locks.create_pin()

            # Get recipient email address
            recipient_email = Lodge.get_booking_email(booking_id=entry)

            # Throw error if we can't get the email
            if "ERROR:" in recipient_email:
                errors.append(recipient_email)
                continue

            if LIVE:
                # Create the guest and PIN
                user_create = locks.create_new_guest(name=booking['guest']['name'],
                                                     email=booking['guest']['email'],
                                                     start=booking['arrival'],
                                                     end=booking['departure'],
                                                     device_id=LISTING_MAPPING[booking['property_id']]['lock_device_id'])

                # Throw error if we can't create the user on the lock
                if isinstance(user_create, str):
                    if "ERROR:" in user_create:
                        errors.append(user_create)
                        continue

                # Send the renter the message with the door code
                message_send = Lodge.send_email_message(
                    subject="Door code for {}, {}".format(booking['guest']['name'], LISTING_MAPPING[booking['property_id']]['display_name']),
                    message=CODE_EMAIL_TEMPLATE.format(pin, RENTAL_CONFIGURATION['check_in_time'],
                                                       RENTAL_CONFIGURATION['check_out_time']),
                    recipient=Lodge.get_booking_email(booking_id=entry))

                # Throw error if we can't send the message to the user
                if isinstance(message_send, str):
                    if "ERROR:" in message_send:
                        errors.append(message_send)
                        continue

                results['codes_sent'].append("*Property:* {}, *Guest:* {} {}-{}\n".format(LISTING_MAPPING[booking['property_id']]['display_name'],
                                                                                          booking['guest']['name'], booking['arrival'], booking['departure']))
                logging.info("----- Created code ({}) for user, effective {} - {}".format(pin,
                                                                                          booking['arrival'],
                                                                                          booking['departure']))
            else:
                logging.info("----- TESTING MODE: Would create and message code to this user.")

    # Report all errors, if we have any
    if errors:
        report_errors(errors)

    # Post to slack
    send_slack_output(results, errors)

if __name__ == "__main__":
    lambda_handler("", "")
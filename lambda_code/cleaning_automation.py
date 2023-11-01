"""
This handles the automation of sending cleaning update message when bookings change.  This is meant to run daily, and it
compares the current bookings in Lodgify to the bookings as known on the last run (and as saved in a JSON file in S3).

It will look for any changes to bookings (new, changed, or cancelled bookings) and if anything has been updated, it will
format and send an email using settings as configured in config.py.

Example email:

Unit 7
----------------------
In: 2022-05-05, Out: 2022-05-08 (Changed!)
In: 2022-05-13, Out: 2022-05-15
In: 2022-05-22, Out: 2022-05-27
In: 2022-05-27, Out: 2022-05-30 (New!)
In: 2022-05-10, Out: 2022-05-20 (Cancelled!)

Unit 6
----------------------
In: 2022-05-27, Out: 2022-05-29 (Changed!)

It will also send a current copy of the cleaning schedule to Slack, with a note as to if there had been any changes, and
if an email was actually sent or not.
"""

from datetime import datetime, timedelta
import boto3
from lodgify import Lodgify
import logging
from config import CLEANING_EMAIL_DESTINATIONS, LISTING_MAPPING, \
    AWS_CONFIGURATION, EMAIL_CONFIGURATION, DAYS_IN_FUTURE_FOR_CLEANINGS, CLEANING_BUCKET_NAME, \
    EMAIL_LINE_COLOR_MAPPINGS
import json
import requests
import os


def send_cleaning_slack_output(body, sent):
    """
    Sends a slack message
    :param body: The message body to send (markdown or plaintext format)
    :param sent: If a cleaning update was sent (bool)
    """

    message_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n\n=================================\nCleaning Email Automation\n=================================\n"
            }
        }
    ]

    # Add note about cleaning message being sent if so
    if sent:
        message_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":siren-flashing: *UPDATES DETECTED! Cleaning email was created and sent, check your inboxes!* :siren-flashing:"
            }
        })

    # Add message body
    message_blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": body
            }
        }
    )

    # Send message
    headers = {
        "Accept": "application/json",
        "Content-type": "application/json"
    }
    message = {
        "text": "The Cleaning Email Automation has run!",
        "blocks": message_blocks
    }

    response = requests.post(os.getenv("SLACK_WEBHOOK"), headers=headers, json=message)


def send_email(message):
    """
    Sends the cleaning update email
    :param message: HTML formatted message with the cleaning details
    """
    client = boto3.client('ses', region_name=AWS_CONFIGURATION['region'])
    client.send_email(
        Source=EMAIL_CONFIGURATION['from_address'],
        Destination={
            "ToAddresses": CLEANING_EMAIL_DESTINATIONS
        },
        Message={
            'Body': {
                'Html': {
                    'Charset': 'UTF-8',
                    'Data': message,
                },
                'Text': {
                    'Charset': 'UTF-8',
                    'Data': message,
                },
            },
            'Subject': {
                'Charset': 'UTF-8',
                'Data': f"Rental Updates {datetime.now().strftime('%m-%d-%Y')}",
            },
        }
    )


class CleaningNotifier:

    def __init__(self):

        self.lodgify_client = Lodgify()
        self.current_bookings = self._get_current_bookings()
        self.previous_bookings = self._get_previous_bookings()
        self.bookings_have_changed = False


    def _save_updated_bookings(self):
        """
        Removes the state from consolidated bookings, and removes any cancelled bookings.  Then it saves the JSON
        to a file in the the S3 bucket configured in config.py
        """
        # Delete any cancelled bookings
        bookings_to_delete =[]
        for unit, bookings in self.consolidated_bookings.items():
            for booking, details in bookings.items():
                if details['state'] == "Cancelled":
                    logging.info(f"-- Removing cancelled booking {booking}")
                    bookings_to_delete.append({
                        "unit": unit,
                        "id": booking
                    })

                # remove state details
                del self.consolidated_bookings[unit][booking]['state']

        for booking in bookings_to_delete:
            del self.consolidated_bookings[booking['unit']][booking['id']]

        logging.info("====")
        logging.info(json.dumps(self.consolidated_bookings,indent=4))

        # save to S3
        s3 = boto3.client('s3')
        s3.put_object(
            Body=json.dumps(self.consolidated_bookings),
            Bucket=CLEANING_BUCKET_NAME,
            Key='rentals.json'
        )


    def _get_previous_bookings(self):
        """
        Pulls the previous booking information from a JSON file in the specified S3 bucket, then loads the JSON
        data
        :return: JSON data of previous bookings

        {
            "Unit X": {
                "XXXXX": {
                    "check_in_date": "2022-05-05",
                    "check_out_date": "2022-05-08",
                    "name": "...",
                    "status": "..."
                },
                ...
            },
            "Unit Y": {
                "YYYYY": {
                    "check_in_date": "2022-05-27",
                    "check_out_date": "2022-05-29",
                    "name": "...",
                    "status": "..."
                },
                ...
            },
            ...
        }
        """

        s3 = boto3.resource('s3')

        content_object = s3.Object(CLEANING_BUCKET_NAME, 'rentals.json')
        file_content = content_object.get()['Body'].read().decode('utf-8')
        json_content = json.loads(file_content)

        logging.info("======== OLD BOOKING DETAILS===========")
        logging.info(json.dumps(json_content, indent=4))
        logging.info("=======================================")

        return json_content


    def _get_current_bookings(self):
        """
        Polls the Lodgify API and gets a list of booking IDs for the configured properties between now and the number
        of days in the future as configured in the config.py file
        :return: list of booking IDs
        """
        # Get start and end dates to search
        start_date = datetime.now().strftime("%m-%d-%Y")
        end_date = (datetime.now() + timedelta(days=DAYS_IN_FUTURE_FOR_CLEANINGS)).strftime("%m-%d-%Y")

        # Get all bookings from Lodgify, for the specified date range
        logging.info("================")
        logging.info("Getting Bookings from Lodgify: {} - {}".format(start_date, end_date))
        logging.info("================")
        logging.info("")
        bookings = self.lodgify_client.get_bookings(start_date=start_date, end_date=end_date)
        return bookings


    def _compare_bookings(self):
        """
        Takes the current bookings from Lodgify and compares them to the previous bookings from the last run. Creates
        a consolidated bookings value, that shows all bookings, and the status (e.g. new, cancelled, updated) for use in
        creating the update email message body
        """

        logging.info("")
        logging.info("================")
        logging.info("Comparing Bookings")
        logging.info("================")
        logging.info("")

        # Find changes from existing booking
        logging.info("Checking previous bookings against current")
        logging.info("-------------------")
        for unit, bookings in self.previous_bookings.items():

            if unit not in self.consolidated_bookings:
                self.consolidated_bookings[unit] = {}

            logging.info(f"{unit}")
            for booking, details in bookings.items():
                logging.info(f"- Checking booking: {booking}")


                if booking not in self.consolidated_bookings[unit]:
                    if details['check_out_date'] == datetime.now().strftime("%Y-%m-%d"):
                        logging.info(f"-- checked out today, skipping")
                        continue

                    logging.info(f"-- cancelled (not in list of current bookings)")
                    self.consolidated_bookings[unit][booking] = details
                    self.consolidated_bookings[unit][booking]['state'] = "Cancelled"
                    self.bookings_have_changed = True
                else:
                    if self.consolidated_bookings[unit][booking] != details:
                        logging.info(f"-- changed (details don't match current bookings:")
                        for key, value in details.items():
                            logging.info(f"---- {key}: {value} (old) / {self.consolidated_bookings[unit][booking][key]} (new)")
                        self.consolidated_bookings[unit][booking]['state'] = "Changed"
                        self.bookings_have_changed = True
                    else:
                        logging.info(f"-- current (all details match)")
                        self.consolidated_bookings[unit][booking]['state'] = "Current"

        # Find new bookings
        logging.info("Checking new bookings against old")
        logging.info("-------------------")
        for unit, bookings in self.consolidated_bookings.items():
            logging.info(f"{unit}")
            for booking in bookings:
                logging.info(f"- Checking booking: {booking}")
                if booking not in self.previous_bookings.get(unit, {}):
                    logging.info(f"-- New (not in old bookings list)")
                    self.consolidated_bookings[unit][booking]['state'] = "New"
                    self.bookings_have_changed = True
                else:
                    logging.info(f"-- Current (in both lists)")


    def _get_details_for_current_bookings(self):
        """
        Polls the Lodgify API for each booking ID, to get the booking details, such as name, dates, booking status,
        messages, etc
        """

        self.consolidated_bookings = {}

        # Go through each booking we have, during the specified window
        logging.info("")
        logging.info("================")
        logging.info("Getting Details For Each Lodgify Booking")
        logging.info("================")
        logging.info("")
        for entry in self.current_bookings:
            logging.info(f"Getting details for booking {entry}")
            booking = self.lodgify_client.get_booking_details(booking_id=entry)

            logging.info(f"- {LISTING_MAPPING[booking['property_id']]['display_name']}, Guest: {booking['guest']['name']}")

            # Add to reservations dict
            if LISTING_MAPPING[booking['property_id']]['display_name'] not in self.consolidated_bookings:
                self.consolidated_bookings[LISTING_MAPPING[booking['property_id']]['display_name']] = {}
            self.consolidated_bookings[LISTING_MAPPING[booking['property_id']]['display_name']][str(entry)] = {
                "check_in_date": booking['arrival'],
                "check_out_date": booking['departure'],
                "name": booking['guest']['name'],
                "status": booking['status']
            }

        logging.info("")
        logging.info("Consolidated Bookings JSON:")
        logging.info("---------")
        logging.info(json.dumps(self.consolidated_bookings, indent=3))
        logging.info("")



    def _format_slack_output(self):
        """
        Formats a block of markdown text to send a slack message update
        :return: markdown formatted message body
        """
        logging.info("")
        logging.info("================")
        logging.info("Formatting Slack Message")
        logging.info("================")
        logging.info("")

        slack_output = "\n"
        for unit, bookings in self.consolidated_bookings.items():
            slack_output += f"{unit}\n"
            slack_output += "----------------------\n"

            for booking, details in bookings.items():

                line = f"{details['name']} - In: {details['check_in_date'][5:]}, Out: {details['check_out_date'][5:]}"
                if details['state'] in ['Changed', 'Cancelled', 'New']:
                    line += f" ({details['state']}!)"

                line += "\n"
                slack_output += line

            slack_output += "\n"

        logging.info(slack_output)
        return slack_output


    def _format_email_output(self):
        """
        Formats the cleaning update email, based on the booking comparison output
        :return: HTML formatted email message body
        """

        logging.info("")
        logging.info("================")
        logging.info("Formatting Cleaning Email")
        logging.info("================")
        logging.info("")

        html_email_output = ""

        for unit, bookings in self.consolidated_bookings.items():
            last_checkout = None
            html_email_output += f"<b>{unit}</b><br>"
            html_email_output += "----------------------<br>"
            logging.info(f"{unit}")
            logging.info("---------------")

            for booking, details in bookings.items():

                if not last_checkout:
                    line = ""
                elif details['check_in_date'][5:] == last_checkout:
                    line = "&nbsp;&nbsp;&nbsp;&nbsp;(*** IS A TURNOVER CLEAN ***)<br>"
                else:
                    line = "<br>"

                if details['state'] in ['Changed', 'Cancelled', 'New']:
                    line += f"""<font style="color:{EMAIL_LINE_COLOR_MAPPINGS[details['state']]}";><b>In:</b> {details['check_in_date'][5:]}, <b>Out:</b> {details['check_out_date'][5:]} ({details['state']}!)</font>"""
                else:
                    line += f"<b>In:</b> {details['check_in_date'][5:]}, <b>Out:</b> {details['check_out_date'][5:]}"

                html_email_output += line
                last_checkout = details['check_out_date'][5:]

            html_email_output += "<br><br>"
            logging.info("")

        return html_email_output


    def send_update_cleaning_email(self):
        """
        Checks all bookings and compares to previous run, to generate and send a new cleaning update email if
        applicable
        """

        self._get_details_for_current_bookings()
        self._compare_bookings()

        # Send the message
        if self.bookings_have_changed:
            email_body = self._format_email_output()
            send_email(message=email_body)
        else:
            logging.info("Not sending email, no updates")

        # Format and send slack message
        slack_output = self._format_slack_output()
        send_cleaning_slack_output(slack_output, self.bookings_have_changed)

        # Save updated bookings back to S3 for future comparison run
        self._save_updated_bookings()



if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logging.basicConfig(format='%(levelname)s:  %(message)s', level=logging.INFO)
    processor = CleaningNotifier()
    processor._get_details_for_current_bookings()

    #processor.send_update_cleaning_email()
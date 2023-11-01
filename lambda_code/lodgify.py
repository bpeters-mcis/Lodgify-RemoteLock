import requests
import json
import os
import logging
from utils import validate_date_input
import boto3
from config import *


class Lodgify:

    def __init__(self):
        self.HEADERS = {
            "Accept": "text/plain",
            "X-ApiKey": os.getenv("LODGIFY_API_KEY"),
            "Content-Type": "application/*+json"
        }


    def get_booking_details(self, booking_id=None):
        """
        Gets the details for a booking
        :param booking_id: The booking to get details for
        :return: a dict of booking details, ex:

            {
               "id": <BOOKING ID>,
               "type": "Booking",
               "booking_type": "InstantBooking",
               "status": "Booked",
               "source": "Manual",
               "source_text": "Direct",
               "guest": {
                  "id": "<GUEST ID>",
                  "country_name": null,
                  "name": "Mark B",
                  "email": null,
                   ...
                  "state": null
               },
               "arrival": "2022-05-27",
               "departure": "2022-05-29",
               "people": 2,
               "property_id": <PROPERTY ID>,
               "property_name": "<PROPERTY NAME>",
               "rooms": [
                  {
                     "name": "<PROPERTY NAME>",
                     "room_type_id": 448939,
                     "people": 2,
                     "key_code": null
                  }
               ],
               "created_at": "2022-04-25T12:49:48",
               "is_replied": true,
               "updated_at": "2022-04-25T12:49:48",
               "is_deleted": false,
               "date_deleted": null,
               "total_amount": 0.0,
               "total_paid": 0.0,
               "amount_to_pay": 0.0,
               "currency": {
                  "id": 50,
                  "code": "USD",
                  "name": "US dollar",
                  "euro_forex": 1.0577,
                  "symbol": "$  "
               },
               "note": null,
               "messages": [
                  {
                     "subject": "<MESSAGE SUBJECT>",
                     "message": "<MESSAGE BODY>",
                     "type": "Owner",
                     "is_replied": true,
                     "created_at": "2022-05-26T14:04:51"
                  },
                  ...
               ],
               "payment_type": null,
               "payment_address": null,
               "payment_website_id": null
            }
        """
        url = "https://api.lodgify.com/v1/reservation/booking/{}".format(booking_id)
        try:
            response = requests.request("GET", url, headers=self.HEADERS)
            details = json.loads(response.text)

            if response.status_code != 200:
                return "ERROR: Failed to get booking details for booking: {}.  Got status code: {}".format(booking_id, response.status_code)
            return details

        except Exception as e:
            return "ERROR: Could not get booking details for {}, got exception error: {}".format(booking_id, e)


    def get_booking_email(self, booking_id=None):
        """
        Gets the email address of the user associated with the provided booking ID
        :param booking_id: The Booking ID to get the email for
        :return: The lodgify email address of the user
        """
        url = "https://api.lodgify.com/v2/reservations/bookings/{}".format(booking_id)
        try:
            response = requests.request("GET", url, headers=self.HEADERS)
            details = json.loads(response.text)

            if response.status_code != 200:
                return "ERROR: Failed to get booking email for booking: {}.  Got status code: {}".format(booking_id, response.status_code)

            return "renter-{}@lodgify.com".format(details['thread_uid'])

        except Exception as e:
            return "ERROR: Could not get booking email for {}, got exception error: {}".format(booking_id, e)


    def get_bookings(self, start_date='01-01-2022', end_date='12-31-2022'):
        """
        Gets all the booking IDs for the configured properties, during the date range specified
        :param start_date: Start date to find bookings (format: MM-DD-YYYY)
        :param end_date: End date to find bookings (format: MM-DD-YYYY)
        :return: A list of booking IDs
        """

        if not validate_date_input(dates=[start_date, end_date]):
            logging.error("WRONG DATES")
            return False

        bookings = []
        url = "https://api.lodgify.com/v1/availability?BookingsOnly=true&IncludeBookingIds=true&periodStart={}&periodEnd={}".format(start_date,
                                                                                                                                    end_date)
        try:
            response = requests.request("GET", url, headers=self.HEADERS)
            details = json.loads(response.text)

            if response.status_code != 200:
                return "ERROR: Failed to get bookings, got {} from Lodgify API".format(response.status_code)
        except Exception as e:
            return "ERROR: Could not get bookings, got exception error: {}".format(e)

        for entry in details:

            # Don't include bookings where the dates are marked "available" for some reason?
            if entry['is_available']:
                logging.info(" -- skipping, marked as available")
                continue

            # Don't include any blocks that don't have associated booking IDs
            if not entry['booking_ids']:
                logging.info(" -- skipping, no booking IDs")
                continue

            # Don't include any properties that are not in our config
            if entry['property_id'] not in LISTING_MAPPING:
                logging.info(" -- skipping, not a tracked property")
                continue

            logging.info("{} is booked from {} to {}, ID {}".format(LISTING_MAPPING[entry['property_id']]['display_name'],
                                                                    entry['period_start'],
                                                                    entry['period_end'],
                                                                    entry['booking_ids'][0]))
            bookings.append(entry['booking_ids'][0])
        return bookings


    def add_message(self, booking_id=None, subject=None, message=None):
        """
        Adds a message to a booking
        :param booking_id: Booking to add message to
        :param subject: Subject of message to send
        :param message: HTML message body to send
        """
        url = "https://api.lodgify.com/v1/reservation/booking/{}/messages".format(booking_id)
        payload = "[{\"subject\":\"" + subject + "\",\"message\":\"" + message + "\",\"type\":\"Owner\"}]"
        response = requests.request("POST", url, data=payload, headers=self.HEADERS)
        logging.info(response.text)


    def send_email_message(self, subject=None, message=None, recipient=None):
        """
        Sends an email message
        :param subject: Email subject
        :param message: Email message body
        :param recipient: Email recipient
        :return:
        """
        try:
            client = boto3.client('ses', region_name=AWS_CONFIGURATION['region'])
            res = client.send_email(
                Source=EMAIL_CONFIGURATION['from_address'],
                Destination={
                    "ToAddresses": [recipient],
                    "BccAddresses": EMAIL_CONFIGURATION['bcc_addresses']
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
                        'Data': subject,
                    },
                }
            )
            return True

        except Exception as e:
            return "ERROR: Could not send email to user: {} Got error: {}".format(recipient, e)

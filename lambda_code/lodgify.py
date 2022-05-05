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

            if entry['is_available']:
                logging.info(".... available?")
                continue

            if not entry['booking_ids']:
                logging.info(".... no booking IDs?")
                continue

            if entry['property_id'] not in LISTING_MAPPING:
                logging.info(".... ID not in config?")
                continue

            logging.info("{} is booked from {} to {}, ID {}".format(LISTING_MAPPING[entry['property_id']]['display_name'],
                                                                    entry['period_start'],
                                                                    entry['period_end'],
                                                                    entry['booking_ids'][0]))
            bookings.append(entry['booking_ids'][0])
        return bookings


    def add_message(self, booking_id=None, subject=None, message=None):
        url = "https://api.lodgify.com/v1/reservation/booking/{}/messages".format(booking_id)
        payload = "[{\"subject\":\"" + subject + "\",\"message\":\"" + message + "\",\"type\":\"Owner\"}]"
        response = requests.request("POST", url, data=payload, headers=self.HEADERS)
        logging.info(response.text)


    def send_email_message(self, subject=None, message=None, recipient=None):
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

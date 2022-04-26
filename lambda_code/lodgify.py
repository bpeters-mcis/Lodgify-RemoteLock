import requests
import json
import os
import logging
from utils import validate_date_input
import boto3


class Lodgify:

    def __init__(self, config):
        self.HEADERS = {
            "Accept": "text/plain",
            "X-ApiKey": os.getenv("LODGIFY_API_KEY"),
            "Content-Type": "application/*+json"
        }

        self.config = config


    def get_booking_details(self, booking_id=None):
        url = "https://api.lodgify.com/v1/reservation/booking/{}".format(booking_id)
        response = requests.request("GET", url, headers=self.HEADERS)
        details = json.loads(response.text)
        return details


    def get_booking_email(self, booking_id=None):
        url = "https://api.lodgify.com/v2/reservations/bookings/{}".format(booking_id)
        response = requests.request("GET", url, headers=self.HEADERS)
        details = json.loads(response.text)
        return "renter-{}@lodgify.com".format(details['thread_uid'])


    def get_bookings(self, start_date='01-01-2022', end_date='12-31-2022'):

        if not validate_date_input(dates=[start_date, end_date]):
            logging.error("WRONG DATES")
            return False

        bookings = []
        url = "https://api.lodgify.com/v1/availability?BookingsOnly=true&IncludeBookingIds=true&periodStart={}&periodEnd={}".format(start_date,
                                                                                                                                    end_date)
        response = requests.request("GET", url, headers=self.HEADERS)
        details = json.loads(response.text)

        for entry in details:

            if entry['is_available']:
                continue

            if not entry['booking_ids']:
                continue

            if entry['property_id'] not in self.config['listings']:
                continue

            logging.info("{} is booked from {} to {}, ID {}".format(self.config['listings'][entry['property_id']]['display_name'],
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
        client = boto3.client('ses', aws_access_key_id=os.getenv('AWS_ID'),
                              aws_secret_access_key=os.getenv('AWS_SECRET'),
                              region_name='us-east-1')
        res = client.send_email(
            Source=self.config['email_configuration']['from_address'],
            Destination={
                "ToAddresses": [recipient],
                "BccAddresses": self.config['email_configuration']['bcc_addresses']
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
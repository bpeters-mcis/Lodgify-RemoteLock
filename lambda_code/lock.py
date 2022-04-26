import requests
import json
import random
import os
import logging


class Lock:

    def __init__(self, config):
        self.host = "https://connect.remotelock.com/"
        self.api_host = "https://api.remotelock.com/"
        self.token = self.get_token()
        self.headers = {
            "Accept": "application/json",
            "Content-type": "application/json",
            "Authorization": "Bearer {}".format(self.token)
        }
        self.config = config


    def get_token(self):
        """
        Gets an oauth token using the client ID and secret
        :return:
        """
        url = "oauth/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        params = {
            "client_id": os.getenv("LOCK_CLIENT"),
            "client_secret": os.getenv("LOCK_SECRET"),
            "grant_type": "client_credentials"
        }
        response = requests.post(self.host + url, headers=headers, params=params)
        if response.status_code != 200:
            return False

        details = json.loads(response.text)
        return details['access_token']


    def send_post_request(self, url, params):
        response = requests.post(self.api_host + url, headers=self.headers, json=params)
        if response.status_code not in [200, 201]:
            logging.error("ERROR! Got status code: {}".format(response.status_code))
            logging.error(response.text)
            exit()

        details = json.loads(response.text)
        return details

    def send_get_request(self, url):
        response = requests.get(self.api_host + url, headers=self.headers)
        if response.status_code != 200:
            logging.error("ERROR! Got status code: {}".format(response.status_code))
            logging.error(response.text)
            exit()

        details = json.loads(response.text)
        return details


    def get_locations(self):
        return self.send_get_request(url="devices")


    def get_schedules(self):
        return self.send_get_request(url="schedules")


    def get_devices(self):
        return self.send_get_request(url="devices")


    def get_device_id_for_unit(self, unit=None):
        devices = self.get_devices()
        for device in devices['data']:
            if unit in device['attributes']['name']:
                return device['id']


    def create_pin(self):
        existing_pins = {}
        existing_users = self.send_get_request(url="access_persons")
        for entry in existing_users['data']:
            existing_pins[entry['attributes']['pin']] = entry['attributes']['name']

        while True:
            new_pin = random.randint(self.config['global_lock_configuration']['random_pin_start'],self.config['global_lock_configuration']['random_pin_end'])
            if new_pin not in existing_pins:
                return new_pin


    def grant_user_access(self, device_id, guest_id):
        # Add Access
        schedule_id = self.config['global_lock_configuration']['schedule_id']
        params = {
            "attributes": {
                "accessible_type": "lock",
                "accessible_id": device_id,
                "access_schedule_id": schedule_id
            }
        }

        response = self.send_post_request(url="access_persons/{}/accesses".format(guest_id), params=params)



    def create_new_user(self, name, email, start, end, pin):

        params = {
            "type": "access_guest",
            "attributes": {
                "starts_at": "{}T{}".format(start, self.config['rental_configuration']['check_in_time']),
                "ends_at": "{}T{}".format(end, self.config['rental_configuration']['check_out_time']),
                "name": name,
                "email": email,
                "pin": pin
            }
        }
        response = self.send_post_request(url="access_persons",
                                          params=params)
        return response['data']['id']


    def create_new_guest(self, name, email, start, end, device_id, pin=None):

        if not pin:
            pin = self.create_pin()
        new_guest_id = self.create_new_user(name=name, email=email, start=start, end=end, pin=pin)
        self.grant_user_access(device_id=device_id, guest_id=new_guest_id)
        return pin

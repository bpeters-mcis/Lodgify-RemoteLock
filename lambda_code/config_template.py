"""
Rename this file to config.py, and fill out each section, based on your environment!
"""

###############
# Email Settings
###############
EMAIL_CONFIGURATION = {
    "error_reporting_destination": "",
    "bcc_addresses": [],
    "from_address": ""
}

CODE_EMAIL_TEMPLATE="""
The code to open the lock for your upcoming rental is: {}.  To unlock the door, enter this code, then
press the "#" button, and the door will unlock.<br><br>

Please note the following:<br>
- The code will not work until {} on the day of your check-in.<br>
- The code will stop working at {} on the day of your check-out.<br><br>

We hope you enjoy your stay!
"""

################
# AWS Configuration
################
AWS_CONFIGURATION = {
    "region": "us-east-1"
}

#################
# Rental Configuration
#################
RENTAL_CONFIGURATION = {
    "check_in_time": "15:00:00",
    "check_out_time": "11:00:00"
}

LISTING_MAPPING = {
    383175: {
        "display_name": "Unit X",
        "lock_device_id": ""
    },
    383176: {
        "display_name": "Unit Y",
        "lock_device_id": ""
    }
}

################
# Cleaning Email Config
################
EMAIL_LINE_COLOR_MAPPINGS = {
    "Cancelled": "red",
    "Changed": "orange",
    "New": "green"
}

DAYS_IN_FUTURE_TO_CHECK = 2
DAYS_IN_FUTURE_FOR_CLEANINGS = 45
CLEANING_EMAIL_DESTINATIONS = []
CLEANING_BUCKET_NAME = "oscodaautomation"

#################
# Lock Configuration
#################
GLOBAL_LOCK_CONFIGURATION = {
    "schedule_id": "",
    "random_pin_start": 10000,
    "random_pin_end": 99999
}
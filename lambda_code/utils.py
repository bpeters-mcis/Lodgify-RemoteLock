import datetime
import logging

def validate_date_input(dates=[]):
    expected_format = "%m-%d-%Y"

    for date in dates:
        try:
            datetime.datetime.strptime(date, expected_format)
            logging.debug("{} is the correct date string format.".format(date))
            return True
        except ValueError:
            logging.error("{} is the incorrect date string format. It should be MM-DD-YYYY".format(date))
            return False
"""
This script was inspired from tmcw's Ruby script doing the same thing:

    https://gist.github.com/tmcw/1098861

And recent fixes implemented thanks to the login structure by wederbrand:

    https://github.com/wederbrand/workout-exchange/blob/master/garmin_connect/download_all.rb

The goal is to iteratively download all detailed information from Garmin Connect
and store it locally for further perusal and analysis. This is still very much
preliminary; future versions should include the ability to seamlessly merge
all the data into a single file, filter by workout type, and other features
to be determined.

2018-04-11 - Garmin appears to have deprecated its old REST api and legacy authentication
The following updates work for me using Python 2.7 and Mechanize
"""

import argparse
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timedelta
from getpass import getpass
try:
    # Python 3
    from urllib.parse import urlencode
except ImportError:
    # Python 2
    from urllib import urlencode

import mechanize as me

BASE_URL = "https://sso.garmin.com/sso/login"
GAUTH = "https://connect.garmin.com/modern/auth/hostname"
SSO = "https://sso.garmin.com/sso"
CSS = "https://static.garmincdn.com/com.garmin.connect/ui/css/gauth-custom-v1.2-min.css"
REDIRECT = "https://connect.garmin.com/modern/"

ACTIVITIES = "https://connect.garmin.com/modern/proxy/activitylist-service/activities/search/activities?start=%s&limit=%s"
WELLNESS = "https://connect.garmin.com/modern/proxy/userstats-service/wellness/daily/%s?fromDate=%s&untilDate=%s"
DAILYSUMMARY = "https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailySummaryChart/%s?date=%s"
STRESS = "https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailyStress/%s"
HEARTRATE = "https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailyHeartRate/%s?date=%s"
SLEEP = "https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailySleepData/%s?date=%s&nonSleepBufferMinutes=60"

TCX = "https://connect.garmin.com/modern/proxy/download-service/export/tcx/activity/%s"
GPX = "https://connect.garmin.com/modern/proxy/download-service/export/gpx/activity/%s"


def get_logger():
    """
    Create logging handler
    """
    ## Create logger
    logger = logging.getLogger('garmindownload')
    logger.setLevel(logging.DEBUG)

    # create file handler which logs even debug messages
    fh = logging.FileHandler('garmindownload.log')
    fh.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)

    # create stdout logger
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


def daterange(start_date, end_date):
    if start_date <= end_date:
        for n in range((end_date - start_date).days + 1):
            yield start_date + timedelta(n)
    else:
        for n in range((start_date - end_date).days + 1):
            yield start_date - timedelta(n)


def get_daterange(start_date, end_date):
    """
    Generate a list with dates of format yyyy-mm-dd from start_date to end_date
    """
    # Append a time to them so there's a smaller chance of error
    start_datetime = datetime.strptime(start_date + ' 11:00', '%Y-%m-%d %H:%M')
    end_datetime = datetime.strptime(end_date + ' 11:00', '%Y-%m-%d %H:%M')
    dates = []
    for date in daterange(start_datetime, end_datetime):
        dates.append(date.strftime('%Y-%m-%d'))
    return dates


def login(logger, agent, username, password):
    global BASE_URL, GAUTH, REDIRECT, SSO, CSS

    agent.set_handle_robots(False)   # no robots
    agent.set_handle_refresh(False)  # can sometimes hang without this
    script_url = 'https://sso.garmin.com/sso/signin?'
    agent.open(script_url)
    agent.addheaders = [('User-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.2 (KHTML, like Gecko) Chrome/15.0.874.121 Safari/535.2')]
    hostname_url = agent.open(GAUTH)
    hostname = json.loads(hostname_url.get_data())['host']

    # Package the full login GET request...
    data = {'service': REDIRECT,
            'webhost': hostname,
            'source': BASE_URL,
            'redirectAfterAccountLoginUrl': REDIRECT,
            'redirectAfterAccountCreationUrl': REDIRECT,
            'gauthHost': SSO,
            'locale': 'en_US',
            'id': 'gauth-widget',
            'cssUrl': CSS,
            'clientId': 'GarminConnect',
            'rememberMeShown': 'true',
            'rememberMeChecked': 'false',
            'createAccountShown': 'true',
            'openCreateAccount': 'false',
            'usernameShown': 'false',
            'displayNameShown': 'false',
            'consumeServiceTicket': 'false',
            'initialFocus': 'true',
            'embedWidget': 'false',
            'generateExtraServiceTicket': 'false'}

    # ...and officially say "hello" to Garmin Connect.
    login_url = 'https://sso.garmin.com/sso/login?%s' % urlencode(data)
    agent.open(login_url)

    # Set up the login form.
    agent.select_form(predicate = lambda f: 'id' in f.attrs and f.attrs['id'] == 'login-form')
    agent['username'] = username
    agent['password'] = password
    agent.set_handle_robots(False)   # no robots
    agent.set_handle_refresh(False)  # can sometimes hang without this
    # Apparently Garmin Connect attempts to filter on these browser headers;
    # without them, the login will fail.

    # Submit the login!
    res = agent.submit()
    if res.get_data().find(b"Invalid") >= 0:
        quit("Login failed! Check your credentials, or submit a bug report.")
    elif res.get_data().find(b"SUCCESS") >= 0:
        logger.info('Login successful! Proceeding...')
    else:
        quit('UNKNOWN STATE. This script may need to be updated. Submit a bug report.')

    # Now we need a very specific URL from the response.
    response_url = re.search("response_url\s*=\s*\"(.*)\";", res.get_data().decode('utf-8')).groups()[0]
    agent.open(response_url.replace("\/", "/"))

    # In theory, we're in.


def file_exists_in_folder(filename, folder):
    "Check if the file exists in folder of any subfolder"
    for _, _, files in os.walk(folder):
        if filename in files:
            return True
    return False


def activities(logger, agent, username, outdir, increment = 100):
    global ACTIVITIES
    currentIndex = 0
    initUrl = ACTIVITIES % (currentIndex, increment)  # 100 activities seems a nice round number
    try:
        response = agent.open(initUrl)
    except:
        logger.warning('Wrong credentials for user {}. Skipping.'.format(username))
        return
    search = json.loads(response.get_data())
    while True:
        if len(search) == 0:
            # All done!
            # print('Download complete')
            break

        for item in search:
            # Read this list of activities and save the files.

            activityId = item['activityId']
            activityDate = item['startTimeLocal'][:10]
            url = TCX % activityId
            file_name = '{}_{}.txt'.format(activityDate, activityId)
            if file_exists_in_folder(file_name, outdir):
                logger.info('{} already exists in {}. Skipping.'.format(file_name, outdir))
                continue
            logger.info('{} is downloading...'.format(file_name))
            datafile = agent.open(url).get_data()
            file_path = os.path.join(outdir, file_name)
            f = open(file_path, "w")
            f.write(datafile)
            f.close()
            shutil.copy(file_path, os.path.join(os.path.dirname(os.path.dirname(file_path)), file_name))

        # We still have at least 1 activity.
        currentIndex += increment
        url = ACTIVITIES % (currentIndex, increment)
        response = agent.open(url)
        search = json.loads(response.get_data())


def wellness(logger, agent, username, start_date, display_name, outdir):
    url = WELLNESS % (display_name, start_date, start_date)
    try:
        response = agent.open(url)
    except:
        logger.warning('Wrong credentials for user {}. Skipping wellness for {}.'.format(username, start_date))
        return
    content = response.get_data().decode('utf-8')

    file_name = '{}_wellness.json'.format(start_date)
    file_path = os.path.join(outdir, file_name)
    with open(file_path, "w") as f:
        f.write(content)


def dailysummary(logger, agent, username, date, display_name, outdir):
    url = DAILYSUMMARY % (display_name, date)
    try:
        response = agent.open(url)
    except:
        logger.warning('Wrong credentials for user {}. Skipping daily summary for {}.'.format(username, date))
        return
    content = response.get_data()

    file_name = '{}_summary.json'.format(date)
    file_path = os.path.join(outdir, file_name)
    with open(file_path, "w") as f:
        f.write(content)


def dailystress(logger, agent, username, date, outdir):
    url = STRESS % (date)
    try:
        response = agent.open(url)
    except:
        logger.warning('Wrong credentials for user {}. Skipping daily stress for {}.'.format(username, date))
        return
    content = response.get_data()

    file_name = '{}_stress.json'.format(date)
    file_path = os.path.join(outdir, file_name)
    with open(file_path, "w") as f:
        f.write(content)


def dailyheartrate(logger, agent, username, date, display_name, outdir):
    url = HEARTRATE % (display_name, date)
    try:
        response = agent.open(url)
    except:
        logger.warning('Wrong credentials for user {}. Skipping daily heart rate for {}.'.format(username, date))
        return
    content = response.get_data()

    file_name = '{}_heartrate.json'.format(date)
    file_path = os.path.join(outdir, file_name)
    with open(file_path, "w") as f:
        f.write(content)


def dailysleep(logger, agent, username, date, display_name, outdir):
    url = SLEEP % (display_name, date)
    try:
        response = agent.open(url)
    except:
        logger.warning('Wrong credentials for user {}. Skipping daily sleep for {}.'.format(username, date))
        return
    content = response.get_data()

    file_name = '{}_sleep.json'.format(date)
    file_path = os.path.join(outdir, file_name)
    with open(file_path, "w") as f:
        f.write(content)


def login_user(logger, username, password):
    # Create the agent and log in.
    agent = me.Browser()
    logger.info("Attempting to login to Garmin Connect...")
    login(logger, agent, username, password)
    return agent


def download_files_for_user(logger, agent, username, output):
    user_output = os.path.join(output, username)
    download_folder = os.path.join(user_output, 'Historical')

    # Create output directory (if it does not already exist).
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    # Scrape all the activities.
    activities(logger, agent, username, download_folder)


def download_wellness_for_user(logger, agent, username, start_date, display_name, output):
    user_output = os.path.join(output, username)
    download_folder = os.path.join(user_output, 'Wellness')

    # Create output directory (if it does not already exist).
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    # Scrape all wellness data.
    wellness(logger, agent, username, start_date, display_name, download_folder)
    # Daily summary, stress and heart rate do not do ranges, only fetch for `startdate`
    dailysummary(logger, agent, username, start_date, display_name, download_folder)
    dailystress(logger, agent, username, start_date, download_folder)
    dailyheartrate(logger, agent, username, start_date, display_name, download_folder)
    dailysleep(logger, agent, username, start_date, display_name, download_folder)


def run_download():
    logger = get_logger()

    parser = argparse.ArgumentParser(description='Garmin Data Scraper',
                                     epilog='Because the hell with APIs!', add_help='How to use',
                                     prog='python download.py [-u <user> | -c <csv fife with credentials>] [ -s <start_date> -e <end_date> -d <display_name> ] -o <output dir>')
    parser.add_argument('-u', '--user', required=False,
                        help='Garmin username. This will NOT be saved!',
                        default=None)
    parser.add_argument('-c', '--csv', required=False,
                        help='CSV file with username and password in "username,password" format.',
                        default=None)
    parser.add_argument('-s', '--startdate', required=False,
                        help='Start date for wellness data',
                        default=None)
    parser.add_argument('-e', '--enddate', required=False,
                        help='End date for wellness data',
                        default=None)
    parser.add_argument('-d', '--displayname', required=False,
                        help='Displayname (see the url when logged into Garmin Connect)',
                        default=None)
    parser.add_argument('-o', '--output', required=False,
                        help='Output directory.', default=os.path.join(os.getcwd(), 'Results/'))
    args = vars(parser.parse_args())

    # Sanity check, before we do anything:
    if args['user'] is None and args['csv'] is None:
        logger.error("Must either specify a username (-u) or a CSV credentials file (-c).")
        sys.exit()

    # Try to use the user argument from command line
    output = args['output']

    if args['user'] is not None:
        password = getpass('Garmin account password (NOT saved): ')
        username = args['user']
    else:
        csv_file_path = args['csv']
        if not os.path.exists(csv_file_path):
            logger.error("Could not find specified credentials file \"%s\"", csv_file_path)
            sys.exit()
        try:
            with open(csv_file_path, 'r') as f:
                contents = f.read()
        except IOError as e:
            logger.error(e)
            sys.exit()
        try:
            username, password = contents.strip().split(",")
        except IndexError:
            logger.error("CSV file must only have 1 line, in \"username,password\" format.")
            sys.exit()

    # Perform the download.
    if args['startdate'] is not None:
        start_date = args['startdate']
        end_date = args['enddate']
        display_name = args['displayname']
        if not end_date:
            logger.error("Provide an enddate")
            sys.exit(1)
        if not display_name:
            logger.error("Provide a displayname, you can find it in the url of Daily Summary: '.../daily-summary/<displayname>/...'")
            sys.exit(1)
        alldates = get_daterange(start_date, end_date)
        agent = login_user(logger, username, password)
        for thisdate in alldates:
            logger.info('Downloading all wellness for %s...', thisdate)
            download_wellness_for_user(logger, agent, username, thisdate, display_name, output)
    else:
        agent = login_user(logger, username, password)
        download_files_for_user(logger, agent, username, output)


if __name__ == "__main__":
    run_download()

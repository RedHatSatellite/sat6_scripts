#!/usr/bin/python
"""Functions common to various Satellite 6 scripts"""

import sys, os, time, yaml, datetime, argparse
import logging

try:
    import requests
except ImportError:
    print "Please install the python-requests module."
    sys.exit(-1)

# Import the site-specific configs
config = yaml.safe_load(open('../config/config.yml', 'r'))

# Read in the config parameters
URL = config["satellite"]["url"]
USERNAME = config["satellite"]["username"]
PASSWORD = config["satellite"]["password"]
LOGDIR = config["logging"]["dir"]
DEBUG = config["logging"]["debug"]


# 'Global' Satellite 6 parameters
# Satellite API
SAT_API = "%s/katello/api/v2/" % URL
# Katello API
KATELLO_API = "%s/katello/api/" % URL
# Foreman_Tasks API
FOREMAN_API = "%s/foreman_tasks/api/" % URL
# HTML Headers for all API POST calls
POST_HEADERS = {'content-type': 'application/json'}


# Define the GET and POST methods
def get_json(location):
    """
    Performs a GET using the passed URL location
    """
    req = requests.get(location, auth=(USERNAME, PASSWORD),\
    verify=True)
    return req.json()

def put_json(location, json_data):
    """
    Performs a PUT and passes the data to the URL location
    """
    result = requests.put(
        location,
        data=json_data,
        auth=(USERNAME, PASSWORD),
        verify=True,
        headers=POST_HEADERS)
    return result.json()

def post_json(location, json_data):
    """
    Performs a POST and passes the data to the URL location
    """
    result = requests.post(
        location,
        data=json_data,
        auth=(USERNAME, PASSWORD),
        verify=True,
        headers=POST_HEADERS)
    return result.json()


def valid_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def get_org_id(org_name):
    """
    Return the Organisation ID for a given Org Name
    """
    # Check if our organization exists, and extract its ID
    org = get_json(SAT_API + "organizations/" + org_name)
    # If the requested organization is not found, exit
    if org.get('error', None):
        print "Organization '%s' does not exist." % org_name
        sys.exit(-1)
    else:
        # Our organization exists, so let's grab the ID and write some debug
        org_id = org['id']
        msg = "Organisation '" + org_name + "' found with ID " + str(org['id'])
        log_msg(msg, 'DEBUG')

    return org_id


# Get details about Content Views and versions
def watch_tasks(task_list, ref_list):
    """
    Watch the status of tasks provided in taskList.
    Loops until all tasks in the list have completed.
    """

    # Seed the pendingList dictionary so all tasks are pending
    pending_list = {}
    for task_id in task_list:
        pending_list[task_id] = "true"

    # Loop through each task and check current status
    do_loop = 1
    sleep_time = 10
    while do_loop == 1:
        if len(task_list) >= 1:
            for task_id in task_list:

                # Whilst there are pending tasks, loop through the task status
                if 'true' in pending_list.values():
                    # Query API to get status of current task
                    status = get_json(
                        FOREMAN_API + "tasks/" + str(task_id))

                    # The result we get back is a floating number - we need to convert to a %
                    pct_done = (status['progress'] * 100)
                    pct_done1 = round(pct_done, 1)

                    print "TASK: " + task_id + " (" + str(ref_list[task_id]) + \
                    ")  STATE: " + str(status['state']) + "  RESULT: "\
                    + str(status['result']) + "  PROGRESS: " + str(pct_done1) \
                    + "%"

                    if status['result'] != "pending":
                        # Update the pendingList dictionary to say this task is done
                        pending_list[task_id] = "false"
                else:
                    # All tasks are complete - end the loop
                    do_loop = 0
                    sleep_time = 0

            # Sleep for 10 seconds between checks
            print "-----\n"
            time.sleep(sleep_time)
        else:
            do_loop = 0
            print "ERROR (watchTasks): no tasks passed to us"

    # All tasks are complete if we get here.
    print "FINISHED"

#-----------------------
# Configure logging
if not os.path.exists(LOGDIR):
    print "Creating log directory"
    os.makedirs(LOGDIR)

logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%b %d %H:%M:%S',
                    filename=(LOGDIR + "/sat6_scripts.log"),
                    filemode='a')

# Suppress logging from requests and urllib3
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

def log_msg(msg, level):
    """Write message to logfile"""

    # If we are NOT in debug mode, only write non-debug messages to the lot
    if level == 'DEBUG':
        if DEBUG:
            logging.debug(msg)
            print msg
    # Otherwise if we ARE in debug, write everything to the log AND stdout
    else:
        logging.info(msg)

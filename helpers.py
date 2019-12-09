#!/usr/bin/python
#title           :helpers.py
#description     :Various helper routines for Satellite 6 scripts
#URL             :https://github.com/ggatward/sat6_scripts
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================

"""Functions common to various Satellite 6 scripts"""

import sys, os, time, datetime, argparse
import logging, tempfile
from time import sleep
from hashlib import sha256
import smtplib

try:
    import requests
except ImportError:
    print "Please install the python-requests module."
    sys.exit(1)

try:
    import yaml
except ImportError:
    print "Please install the PyYAML module."
    sys.exit(1)


# Import the site-specific configs
dir = os.path.dirname(__file__)
filename = os.path.join(dir, 'config/config.yml')
CONFIG = yaml.safe_load(open(filename, 'r'))

# Read in the config parameters
URL = CONFIG['satellite']['url']
USERNAME = CONFIG['satellite']['username']
PASSWORD = CONFIG['satellite']['password']
DISCONNECTED = CONFIG['satellite']['disconnected']
if 'manifest' in CONFIG['satellite']:
    MANIFEST = CONFIG['satellite']['manifest']
ORG_NAME = CONFIG['satellite']['default_org']
PXYADDR = None
if 'proxy' in CONFIG['satellite']:
    PXYADDR = CONFIG['satellite']['proxy']
LOGDIR = CONFIG['logging']['dir']
DEBUG = CONFIG['logging']['debug']
EXPORTDIR = CONFIG['export']['dir']
IMPORTDIR = CONFIG['import']['dir']
if 'syncbatch' in CONFIG['import']:
    SYNCBATCH = CONFIG['import']['syncbatch']
else:
    SYNCBATCH = 255
if 'batch' in CONFIG['publish']:
    PUBLISHBATCH = CONFIG['publish']['batch']
else:
    PUBLISHBATCH = 255
if 'batch' in CONFIG['promotion']:
    PROMOTEBATCH = CONFIG['promotion']['batch']
else:
    PROMOTEBATCH = 255
if 'mailout' in CONFIG['email']:
    MAILOUT = CONFIG['email']['mailout']
else:
    MAILOUT = False
if 'mailfrom' in CONFIG['email']:
    MAILFROM = CONFIG['email']['mailfrom']
if 'mailto' in CONFIG['email']:
    MAILTO = CONFIG['email']['mailto']
if 'servertype' in CONFIG['puppet-forge-server']:
    PFMETHOD = CONFIG['puppet-forge-server']['servertype']
else:
    PFMETHOD = 'puppet-forge-server'
if 'hostname' in CONFIG['puppet-forge-server']:
    PFSERVER = CONFIG['puppet-forge-server']['hostname']
if 'modulepath' in CONFIG['puppet-forge-server']:
    PFMODPATH = CONFIG['puppet-forge-server']['modulepath']
if 'username' in CONFIG['puppet-forge-server']:
    PFUSER = CONFIG['puppet-forge-server']['username']
else:
    PFUSER = runuser
if 'token' in CONFIG['puppet-forge-server']:
    PFTOKEN = CONFIG['puppet-forge-server']['token']

# 'Global' Satellite 6 parameters
# Satellite API
SAT_API = "%s/katello/api/v2/" % URL
# Katello API
KATELLO_API = "%s/katello/api/" % URL
# Foreman_Tasks API
FOREMAN_API = "%s/foreman_tasks/api/" % URL
# HTML Headers for all API POST calls
POST_HEADERS = {'content-type': 'application/json'}

# Define our global message colours
PURPLE = '\033[95m'
BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
HEADER = PURPLE
WARNING = YELLOW
ERROR = RED
ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'

# Mailout pre-canned subjects
MAILSUBJ_FI = "Satellite 6 import failure"
MAILSUBJ_FP = "Satellite 6 publish/promote failure"

def who_is_running():
    """ Return the OS user that is running the script """
    # Who is running this script?
    if os.environ.get('SUDO_USER'):
        runuser = str(os.environ.get('SUDO_USER'))
    else:
        runuser = 'root'
    return runuser


# Define the GET and POST methods
def get_json(location):
    """
    Performs a GET using the passed URL location
    """
    result = requests.get(
        location,
        auth=(USERNAME, PASSWORD),
        verify=True)
    return result.json()

def get_p_json(location, json_data):
    """
    Performs a GET with input data to the URL location
    """
    result = requests.get(
        location,
        data=json_data,
        auth=(USERNAME, PASSWORD),
        verify=True,
        headers=POST_HEADERS)
    return result.json()

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


def valid_date(indate):
    """
    Check date format is valid
    """
    try:
        return datetime.datetime.strptime(indate, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(indate)
        raise argparse.ArgumentTypeError(msg)


def sha256sum(filename):
    """
    Perform sha256sum of given file
    """
    f_name = open(filename, 'rb')
    shasum = (sha256(f_name.read()).hexdigest(), filename)
    return shasum


def disk_usage(path):
    """Return disk usage associated with path, in percent."""
    stat = os.statvfs(path)
    total = (stat.f_blocks * stat.f_frsize)
    used = (stat.f_blocks - stat.f_bfree) * stat.f_frsize
    try:
        percent = (float(used) / total) * 100
    except ZeroDivisionError:
        percent = 0
    return round(percent, 1)


def get_org_id(org_name):
    """
    Return the Organisation ID for a given Org Name
    """
    # Check if our organization exists, and extract its ID
    org = get_json(SAT_API + "organizations/" + org_name)
    # If the requested organization is not found, exit
    if org.get('error', None):
        msg = "Organization '%s' does not exist." % org_name
        log_msg(msg, 'ERROR')
        sys.exit(1)
    else:
        # Our organization exists, so let's grab the ID and write some debug
        org_id = org['id']
        msg = "Organisation '" + org_name + "' found with ID " + str(org['id'])
        log_msg(msg, 'DEBUG')

    return org_id

def get_org_label(org_name):
    """
    Return the Organisation label for a given Org Name
    """
    # Check if our organization exists, and extract its label
    org = get_json(SAT_API + "organizations/" + org_name)
    # If the requested organization is not found, exit
    if org.get('error', None):
        msg = "Organization '%s' does not exist." % org_name
        log_msg(msg, 'ERROR')
        sys.exit(1)
    else:
        # Our organization exists, so let's grab the label and write some debug
        org_label = org['label']
        msg = "Organisation '" + org_name + "' found with label " + org['label']
        log_msg(msg, 'DEBUG')

    return org_label


class ProgressBar:
    def __init__(self, duration):
        self.duration = duration
        self.prog_bar = '[]'
        self.fill_char = '#'
        self.width = 60
        self.__update_amount(0)

    def animate(self):
        for i in range(self.duration):
            if sys.platform.lower().startswith('win'):
                print self, '\r',
            else:
                print self, chr(27) + '[A'
            self.update_time(i + 0.5)
            time.sleep(0.5)
        print self

    def update_time(self, elapsed_pct):
        self.__update_amount((elapsed_pct / float(self.duration)) * 100.0)
        self.prog_bar += '  %d%%' % (elapsed_pct)

    def __update_amount(self, new_amount):
        percent_done = int(round((new_amount / 100.0) * 100.0))
        all_full = self.width - 2
        num_hashes = int(round((percent_done / 100.0) * all_full))
        self.prog_bar = '[' + self.fill_char * num_hashes + ' ' * (all_full - num_hashes) + ']'

    def __str__(self):
        return str(self.prog_bar)


def wait_for_task(task_id, label):
    """
    Wait for the given task ID to complete
    This displays a message without CR/LF waiting for an OK/FAIL status to be shown
    """
    msg = "  Waiting for " + label + " to complete..."
    colx = "{:<70}".format(msg)
    print colx[:70],
    log_msg(msg, 'INFO')
    # Force the status message to be shown to the user
    sys.stdout.flush()
    while True:
        info = get_json(FOREMAN_API + "tasks/" + str(task_id))
        if info['state'] == 'paused' and info['result'] == 'error':
            msg = "Error with " + label + " " + str(task_id)
            log_msg(msg, 'ERROR')
            break
        if info['pending'] != 1:
            break
        sleep(30)


def get_task_status(task_id):
    """Check of the status of the given task ID"""
    info = get_json(FOREMAN_API + "tasks/" + str(task_id))
    if info['state'] != 'running':
        error_info = info['humanized']['errors']
        for error_detail in error_info:
            msg = error_detail
            log_msg(msg, 'ERROR')
    return info


# Get details about Content Views and versions
def watch_tasks(task_list, ref_list, task_name, quiet):
    """
    Watch the status of tasks provided in taskList.
    Loops until all tasks in the list have completed.
    """

    # Seed the pendingList dictionary so all tasks are pending
    pending_list = {}
    for task_id in task_list:
        pending_list[task_id] = "true"

    # Loop through each task and check current status
    do_loop = True
    sleep_time = 10
    failure = False
    while do_loop:
        if len(task_list) >= 1:
            # Don't render progress bars if in quiet mode
            if not quiet:
                os.system('clear')
                print BOLD + task_name + ENDC

            for task_id in task_list:

                # Whilst there are pending tasks, loop through the task status
                if 'true' in pending_list.values():
                    # Query API to get status of current task
                    status = get_json(
                        FOREMAN_API + "tasks/" + str(task_id))

                    # The result we get back is a floating number - we need to convert to a %
                    pct_done = (status['progress'] * 100)
                    pct_done1 = round(pct_done, 1)

                    if status['result'] == 'success':
                        colour = GREEN
                    elif status['result'] == 'pending':
                        colour = YELLOW
                    else:
                        colour = RED
                        failure = True

                    # Call the progress bar class
                    p = ProgressBar(100)
                    p.update_time(pct_done1)
                    # Don't render progress bars if in quiet mode
                    if not quiet:
                        print colour + str(ref_list[task_id]) + ':' + ENDC
                        print p

                    if status['result'] != "pending":
                        # Update the pendingList dictionary to say this task is done
                        pending_list[task_id] = "false"
                else:
                    # All tasks are complete - end the loop
                    do_loop = False
                    sleep_time = 0
                    continue

            # Sleep for 10 seconds between checks
            time.sleep(sleep_time)
        else:
            do_loop = False
            print "ERROR (watchTasks): no tasks passed to us"

    # All tasks are complete if we get here.
    msg = task_name + " complete"
    log_msg(msg, 'INFO')
    if failure:
        print RED + "\nNot all tasks completed successfully" + ENDC
    else:
        print GREEN + "\nAll tasks complete" + ENDC


def check_running_sync():
    """
    Check for any currently running Sync tasks
    Exits script if any Synchronize or Export tasks are found in a running state.
    """
    tasks = get_json(
        FOREMAN_API + "tasks/")

    # From the list of tasks, look for any running sync jobs.
    # If e have any we exit, as we can't trigger a new sync in this state.
    for task_result in tasks['results']:
        if task_result['state'] == 'running' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Synchronize':
                msg = "Unable to start sync - a Sync task is currently running"
                log_msg(msg, 'ERROR')
                sys.exit(1)
        if task_result['state'] == 'paused' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Synchronize':
                msg = "Unable to start sync - a Sync task is paused. Resume any paused sync tasks."
                log_msg(msg, 'ERROR')
                sys.exit(1)


def check_running_publish(cvid, desc):
    """
    Check for any currently running Promotion/Publication tasks
    Exits script if any Publish/Promote tasks are found in a running state.
    """
    #pylint: disable-msg=R0912,R0914,R0915
    tasks = get_json(
        FOREMAN_API + "tasks/")

    # From the list of tasks, look for any running sync jobs.
    # If e have any we exit, as we can't trigger a new sync in this state.
    for task_result in tasks['results']:
        if task_result['state'] == 'planning' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Publish':
                msg = "Unable to start '" + desc + "': A publish task is in planning state, cannot determine if it is for this CV"
                log_msg(msg, 'WARNING')
                locked = True
                return locked
        if task_result['state'] == 'running' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Publish':
                if task_result['input']['content_view']['id'] == cvid:
                    msg = "Unable to start '" + desc + "': content view is locked by a running Publish task"
                    log_msg(msg, 'WARNING')
                    locked = True
                    return locked
        if task_result['state'] == 'paused' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Publish':
                if task_result['input']['content_view']['id'] == cvid:
                    msg = "Unable to start '" + desc + "': content view is locked by a paused Publish task"
                    log_msg(msg, 'WARNING')
                    locked = True
                    return locked
        if task_result['state'] == 'planning' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Promotion' or task_result['humanized']['action'] == 'Promote':
                msg = "Unable to start '" + desc + "': A promotion task is in planning state, cannot determine if it is for this CV"
                log_msg(msg, 'WARNING')
                locked = True
                return locked
        if task_result['state'] == 'running' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Promotion' or task_result['humanized']['action'] == 'Promote':
                if task_result['input']['content_view']['id'] == cvid:
                    msg = "Unable to start '" + desc + "': content view is locked by a running Promotion task"
                    log_msg(msg, 'WARNING')
                    locked = True
                    return locked
        if task_result['state'] == 'paused' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Promotion' or task_result['humanized']['action'] == 'Promote':
                if task_result['input']['content_view']['id'] == cvid:
                    msg = "Unable to start '" + desc + "': content view is locked by a paused Promotion task"
                    log_msg(msg, 'WARNING')
                    locked = True
                    return locked
        if task_result['state'] == 'planning' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Remove Versions and Associations':
                msg = "Unable to start '" + desc + "': A remove task is in planning state, cannot determine if it is for this CV"
                log_msg(msg, 'WARNING')
                locked = True
                return locked
        if task_result['state'] == 'running' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Remove Versions and Associations':
                if task_result['input']['content_view']['id'] == cvid:
                    msg = "Unable to start '" + desc + "': content view is locked by a running CV deletion task"
                    log_msg(msg, 'WARNING')
                    locked = True
                    return locked
        if task_result['state'] == 'paused' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Remove Versions and Associations':
                if task_result['input']['content_view']['id'] == cvid:
                    msg = "Unable to start '" + desc + "': content view is locked by a paused CV deletion task"
                    log_msg(msg, 'WARNING')
                    locked = True
                    return locked



def query_yes_no(question, default="yes"):
    """
    Ask a yes/no question via raw_input() and return their answer.

    'question' is a string that is presented to the user.
    'default' is the presumed answer if the user just hits <Enter>.
        It must be 'yes' (the default), 'no' or None (meaning
        an answer is required of the user).

    The 'answer' return value is True for 'yes' or False for 'no'.
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def mailout(subject, message):
    """
    Function to handle simple SMTP mailouts for alerting.
    Assumes localhost is configured for SMTP forwarding (postfix)
    """
    sender = MAILFROM
    receivers = MAILTO

    body = 'From: {}\nSubject: {}\n\n{}'.format(sender, subject, message)

    smtpObj = smtplib.SMTP('localhost')
    smtpObj.sendmail(sender, receivers, body)


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

# Open a temp file to hold the email output
tf = tempfile.NamedTemporaryFile()

def log_msg(msg, level):
    """Write message to logfile"""

    # If we are NOT in debug mode, only write non-debug messages to the log
    if level == 'DEBUG':
        if DEBUG:
            logging.debug(msg)
            print BOLD + "DEBUG: " + msg + ENDC
    elif level == 'ERROR':
        logging.error(msg)
        tf.write('ERROR:' + msg + '\n')
        print ERROR + "ERROR: " + msg + ENDC
    elif level == 'WARNING':
        logging.warning(msg)
        tf.write('WARNING:' + msg + '\n')
        print WARNING + "WARNING: " + msg + ENDC
    # Otherwise if we ARE in debug, write everything to the log AND stdout
    else:
        logging.info(msg)
        tf.write(msg + '\n')

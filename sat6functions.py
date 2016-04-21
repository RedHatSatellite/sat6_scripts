#!/usr/bin/python
"""Functions common to many Satellite 6 scripts"""

#import sys, json, time
import sys, time
import config

try:
    import requests
except ImportError:
    print "Please install the python-requests module."
    sys.exit(-1)


# 'Global' Satellite 6 parameters
# Satellite API
SAT_API = "%s/katello/api/v2/" % config.URL
# Katello API
KATELLO_API = "%s/katello/api/" % config.URL
# Foreman_Tasks API
FOREMAN_API = "%s/foreman_tasks/api/" % config.URL
# HTML Headers for all API POST calls
POST_HEADERS = {'content-type': 'application/json'}



# Define the GET and POST methods
def get_json(location):
    """
    Performs a GET using the passed URL location
    """
    req = requests.get(location, auth=(config.USERNAME, config.PASSWORD),\
    verify=config.SSL_VERIFY)
    return req.json()

def put_json(location, json_data):
    """
    Performs a POST and passes the data to the URL location
    """
    result = requests.put(
        location,
        data=json_data,
        auth=(config.USERNAME, config.PASSWORD),
        verify=config.SSL_VERIFY,
        headers=POST_HEADERS)
    return result.json()

def post_json(location, json_data):
    """
    Performs a POST and passes the data to the URL location
    """
    result = requests.post(
        location,
        data=json_data,
        auth=(config.USERNAME, config.PASSWORD),
        verify=config.SSL_VERIFY,
        headers=POST_HEADERS)
    return result.json()

# Get details about Content Views and versions
def watch_tasks(task_list, ref_list):
    """
    Get the status of tasks provided in taskList
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

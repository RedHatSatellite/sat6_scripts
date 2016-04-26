#!/usr/bin/python
"""
Removes unused Content View versions from each environment.

NOTE:  This file is managed by the STASH git repository. Any modifications to
       this file must be made in the source repository and then deployed.
"""

import sys, argparse
import simplejson as json
import sat6functions, config
from time import sleep
import logging

# global debug
DEBUG = 1

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(message)s',
                    datefmt='%b %d %H:%M:%S',
                    filename=config.LOGFILE,
                    filemode='w')

#-----------------------

def log_message(msg, level):
    """Write message to logfile"""
    # Everything is written to file:
    logging.info(level + " " + msg)
    # But we only output non-debug to stdout unless debug is set
    if not DEBUG:
        if level != 'DEBUG':
            print msg
    else:
        print msg

# Get details about Content Views and versions
def get_content_views(org_id):
    """Returns a list of all Content View IDs and Names for a given Org ID"""
    # Query API to get all content views for our org
    cvlist = []
    cv_list = sat6functions.get_json(
        sat6functions.KATELLO_API + "organizations/" + str(org_id) +
        "/content_views/")
    for cv_results in cv_list['results']:
        cvl = {}
        cvl['id'] = cv_results.get('id')
        cvl['name'] = cv_results.get('name')
        cvlist.append(cvl)

    return cvlist

def get_content_view_info(cvid):
    """Return Content View Info for a given CV ID"""
    cv_info = sat6functions.get_json(
        sat6functions.KATELLO_API + "content_views/" + str(cvid))
    return cv_info

def remove_content_view_version(cv_id, version_id):
    """Removes Content View version, given the Content View ID and the
    Version to delete."""
    msg = "Removing Content View with ID=" + str(cv_id) + " and version ID="\
    + str(version_id)
    log_message(msg, 'INFO')
    rinfo = sat6functions.put_json(
        sat6functions.KATELLO_API + "content_views/" + str(cv_id) + "/remove/",
        json.dumps({
            "id": cv_id,
            "content_view_version_ids": version_id
            }))

    return rinfo

def wait_for_task(task_id):
    """Wait for the given task ID to complete"""
    msg = "Waiting for Task " + str(task_id) + " to finish"
    log_message(msg, 'INFO')
    while True:
        info = sat6functions.get_json(sat6functions.FOREMAN_API + "tasks/"\
        + str(task_id))
        if info['state'] == 'paused' and info['result'] == 'error':
            msg = "Error with Content View Update " + str(task_id)
            log_message(msg, 'ERROR')
            break
        if info['pending'] != 1:
            break
        sleep(30)

def get_task_status(task_id):
    """Check of the status of the given task ID"""
    info = sat6functions.get_json(sat6functions.FOREMAN_API + "tasks/"\
    + str(task_id))
    if info['state'] != 'running':
        error_info = info['humanized']['errors']
        for error_detail in error_info:
            msg = error_detail
            log_message(msg, 'ERROR')
    return info

def main():
    """Main Routine"""
    # Check for sane input
    parser = argparse.ArgumentParser(description='Removes unused Content Views \
    for specified organization.')
    parser.add_argument('-o', '--org', help='Organization', required=True)
    args = parser.parse_args()

    # Set our script variables from the input args
    org_name = args.org

    # Check if our organization exists, and extract its ID
    org = sat6functions.get_json(sat6functions.SAT_API + "organizations/"\
    + org_name)
    # If our organization is not found, exit
    if org.get('error', None):
        print "Organization '%s' does not exist." % org_name
        sys.exit(-1)
    else:
        # Our organization exists, so let's grab the ID
        org_id = org['id']

    # Get the list of content views
    cvlist = get_content_views(org_id)

    if cvlist:
        for cv_results in cvlist:
            cvinfo = get_content_view_info(cv_results['id'])
            for version in cvinfo['versions']:
                if not version['environment_ids']:
                    # Delete the content view version
                    cvrtask = remove_content_view_version(cv_results['id'],\
                    version['id'])
                    # Wait for it to complete
                    wait_for_task(cvrtask['id'])

                    # Check if it completed OK
                    tinfo = get_task_status(cvrtask['id'])
                    if tinfo['state'] != 'running' and tinfo['result'] == \
                    'success':
                        msg = "Content View Removal for ID="\
                        + str(version['id']) + " OK"
                        log_message(msg, 'INFO')
                    else:
                        msg = "Content View Removal for ID="\
                        + str(version['id']) + " FAIL"
                        log_message(msg, 'INFO')
    else:
        # Unable to get CV list
        msg = "Unable to get Content View List"
        log_message(msg, 'INFO')
        sys.exit(1)


if __name__ == "__main__":
    main()

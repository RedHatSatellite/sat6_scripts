#!/usr/bin/python
#title           :clean_content_view.py
#description     :Removes orphaned versions of Satellite 6 content views
#URL             :https://github.com/ggatward/sat6_scripts
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Removes content view versions that don't belong to any environment

"""
#pylint: disable-msg=R0912,R0913,R0914,R0915

import sys, argparse
import simplejson as json
import helpers


def get_cv(org_id, cleanup_list, exclude_list):
    """Get the content views"""

    if cleanup_list:
        cleanstring = ', '.join(str(e) for e in cleanup_list)
        msg = "Cleaning only specified content view '" + cleanstring + "'"
        helpers.log_msg(msg, 'DEBUG')

    if exclude_list:
        exstring = ', '.join(str(e) for e in exclude_list)
        msg = "Cleaning all content views except '" + exstring + "'"
        helpers.log_msg(msg, 'DEBUG')


    # Query API to get all content views for our org
    cvs = helpers.get_json(
        helpers.KATELLO_API + "organizations/" + str(org_id) + "/content_views/")
    ver_list = {}
    ver_descr = {}

    for cv_result in cvs['results']:
        # We will never clean the DOV
        if cv_result['name'] != "Default Organization View":

            # Handle specific includes and excludes
            if cleanup_list and cv_result['name'] not in cleanup_list:
                msg = "Skipping content view '" + cv_result['name'] + "'"
                helpers.log_msg(msg, 'DEBUG')
                continue

            if exclude_list and cv_result['name'] in exclude_list:
                msg = "Skipping content view '" + cv_result['name'] + "'"
                helpers.log_msg(msg, 'DEBUG')
                continue

            # Get the ID of each Content View
            msg = "Processing content view '" + cv_result['name'] + "' " + str(cv_result['id'])
            helpers.log_msg(msg, 'DEBUG')

            # Find the next version of the view
            ver_list[cv_result['id']] = cv_result['id']
            ver_descr[cv_result['id']] = cv_result['name']

    return ver_list, ver_descr


def get_content_view_info(cvid):
    """
    Return Content View Info for a given CV ID
    """
    cvinfo = helpers.get_json(
        helpers.KATELLO_API + "content_views/" + str(cvid))

    return cvinfo


def cleanup(ver_list, ver_descr, dry_run, runuser):
    """Clean Content Views"""

    # Set the task name to be displayed in the task monitoring stage
    task_name = "Cleanup content views"

    # Now we have all the info needed, we can actually trigger the cleanup.
    task_list = []
    ref_list = {}

    # Catch scenario that no CV versions are found matching cleanup criteria
    if not ver_list:
        msg = "No content view versions found matching cleanup criteria"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    for cvid in ver_list.keys():

        # Check if there is a publish/promote already running on this content view
        locked = helpers.check_running_publish(ver_list[cvid], ver_descr[cvid])

        # For the given content view we need to find the orphaned versions
        cvinfo = get_content_view_info(cvid)

        for version in cvinfo['versions']:
            # Find versions that are not in any environment
            if not version['environment_ids']:
                if not locked:
                    msg = "Orphan view id " + str(version['id']) + " found in '" +\
                        str(ver_descr[cvid]) + "'"
                    helpers.log_msg(msg, 'DEBUG')
                    msg = "Removing '" + str(ver_descr[cvid]) + "' version " + str(version['version'])
                    helpers.log_msg(msg, 'INFO')
                    print helpers.HEADER + msg + helpers.ENDC

                # Delete the view version from the content view
                if not dry_run and not locked:
                    try:
                        task_id = helpers.put_json(
                            helpers.KATELLO_API + "content_views/" + str(cvid) + "/remove/",
                            json.dumps(
                                {
                                    "id": cvid,
                                    "content_view_version_ids": version['id']
                                }
                                ))['id']

                        # Wait for the task to complete
                        helpers.wait_for_task(task_id)

                        # Check if the deletion completed successfully
                        tinfo = helpers.get_task_status(task_id)
                        if tinfo['state'] != 'running' and tinfo['result'] == 'success':
                            msg = "Removal of content view version OK"
                            helpers.log_msg(msg, 'INFO')
                            print helpers.GREEN + "OK" + helpers.ENDC
                        else:
                            msg = "Failed"
                            helpers.log_msg(msg, 'ERROR')

                    except Warning:
                        msg = "Failed to initiate removal"
                        helpers.log_msg(msg, 'WARNING')


    # Exit in the case of a dry-run
    if dry_run:
        msg = "Dry run - not actually performing removal"
        helpers.log_msg(msg, 'WARNING')
        sys.exit(-1)


def main():
    """
    Main routine
    """

    # Who is running this script?
    runuser = helpers.who_is_running()

    # Check for sane input
    parser = argparse.ArgumentParser(
        description='Cleans content views for specified organization.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization', required=True)
    group.add_argument('-x', '--exfile',
        help='Cleans all content views EXCEPT those listed in file', required=False)
    group.add_argument('-i', '--infile', help='Clean only content views listed in file',
        required=False)
    group.add_argument('-a', '--all', help='Clean ALL content views', required=False,
        action="store_true")
    parser.add_argument('-d', '--dryrun', help='Dry Run - Only show what will be cleaned',
        required=False, action="store_true")

    args = parser.parse_args()

    # Log the fact we are starting
    msg = "-------- Content view cleanup started by " + runuser + " -----------"
    helpers.log_msg(msg, 'INFO')

    # Set our script variables from the input args
    org_name = args.org
    dry_run = args.dryrun
    cleanup_file = args.infile
    exclude_file = args.exfile

    if not exclude_file and not cleanup_file and not args.all:
        msg = "Content view to clean not specified, and 'all' was not selected"
        helpers.log_msg(msg, 'WARNING')
        answer = helpers.query_yes_no("Proceed to clean ALL content views?", "no")
        if not answer:
            msg = "Cleanup aborted by user"
            helpers.log_msg(msg, 'INFO')
            sys.exit(-1)

    # Read in the exclusion file to the exclude list
    exclude_list = []
    cleanup_list = []
    if exclude_file or cleanup_file:
        try:
            if exclude_file:
                xfile = open(exclude_file, 'r')
                exclude_list = [line.rstrip('\n') for line in xfile]
            if cleanup_file:
                xfile = open(cleanup_file, 'r')
                cleanup_list = [line.rstrip('\n') for line in xfile]
        except IOError:
            msg = "Cannot find input file"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(-1)

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Get the list of Content Views along with the latest view version in each environment
    (ver_list, ver_descr) = get_cv(org_id, cleanup_list, exclude_list)

    # Clean the content views. Returns a list of task IDs.
    cleanup(ver_list, ver_descr, dry_run, runuser)


if __name__ == "__main__":
    main()


#!/usr/bin/python
#title           :clean_content_views.py
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

def get_cv(org_id, cleanup_list, keep):
    """Get the content views"""

    # Query API to get all content views for our org
    cvs = helpers.get_json(
        helpers.KATELLO_API + "organizations/" + str(org_id) + "/content_views/")
    ver_list = {}
    ver_descr = {}
    ver_keep = {}

    for cv_result in cvs['results']:
        # We will never clean the DOV
        if cv_result['name'] != "Default Organization View":
            # Handle specific includes
            if cleanup_list:
                # The list contains dictionaries as elements. Process each dictionary
                for cv in cleanup_list:
                    # If the CV name does not appear in our config list, skip
                    if cv['view'] != cv_result['name']:
                        msg = "Skipping " + cv_result['name']
                        helpers.log_msg(msg, 'DEBUG')
                        continue
                    else:
                        msg = "Processing content view '" + cv_result['name'] + "' " \
                            + str(cv_result['id'])
                        helpers.log_msg(msg, 'DEBUG')

                        # Add the next version of the view, and how many versions to keep
                        ver_list[cv_result['id']] = cv_result['id']
                        ver_descr[cv_result['id']] = cv_result['name']
                        ver_keep[cv_result['id']] = cv['keep']

            # Handle the 'all' option
            else:
                msg = "Processing content view '" + cv_result['name'] + "' " \
                    + str(cv_result['id'])
                helpers.log_msg(msg, 'DEBUG')

                # Add the next version of the view, and how many versions to keep
                ver_list[cv_result['id']] = cv_result['id']
                ver_descr[cv_result['id']] = cv_result['name']
                ver_keep[cv_result['id']] = keep


    return ver_list, ver_descr, ver_keep


def get_content_view_info(cvid):
    """
    Return Content View Info for a given CV ID
    """
    cvinfo = helpers.get_json(
        helpers.KATELLO_API + "content_views/" + str(cvid))

    return cvinfo


def cleanup(ver_list, ver_descr, dry_run, runuser, ver_keep):
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

        msg = "Cleaning '" + str(ver_descr[cvid]) 
        helpers.log_msg(msg, 'INFO')
        print helpers.HEADER + msg + helpers.ENDC

        # For the given content view we need to find the orphaned versions
        cvinfo = get_content_view_info(cvid)

        # Find the oldest published version
        version_list = []
        for version in cvinfo['versions']:
            if not version['environment_ids']:
                continue
            else:
                msg = "Found version " + str(version['version'])
                helpers.log_msg(msg, 'DEBUG')
                # Add the version id to a list
                version_list.append(float(version['version']))
        # Find the oldest 'in use' version id
        lastver = min(version_list)

        msg = "Oldest in-use version is " + str(lastver)
        helpers.log_msg(msg, 'DEBUG')

        for version in cvinfo['versions']:
            # Find versions that are not in any environment
            if not version['environment_ids']:
                if not locked:
                    msg = "Orphan view version " + str(version['version']) + " found in '" +\
                        str(ver_descr[cvid]) + "'"
                    helpers.log_msg(msg, 'DEBUG')

                    if float(version['version']) > float(lastver):
                        msg = "Skipping delete of " + str(version['version'])
                        helpers.log_msg(msg, 'INFO')
                        print msg
                        continue
                    else:
                        if float(version['version']) < (lastver - float(ver_keep[cvid])):
                            msg = "Removing '" + str(ver_descr[cvid]) + "' version " +\
                                str(version['version'])
                            helpers.log_msg(msg, 'INFO')
                            print helpers.HEADER + msg + helpers.ENDC
                        else:
                            msg = "Skipping delete of " + str(version['version']) + " due to --keep value"
                            helpers.log_msg(msg, 'INFO')
                            print msg
                            continue

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
                        helpers.wait_for_task(task_id,'clean')

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
    parser.add_argument('-o', '--org', help='Organization (Uses default if not specified)',
        required=False)
    parser.add_argument('-k', '--keep', help='How many old versions to keep (only used with -a)',
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
    if args.org:
        org_name = args.org
    else:
       org_name = helpers.ORG_NAME
    dry_run = args.dryrun
    if args.keep:
        keep = args.keep
    else:
        keep = "0"

    cleanup_list = []
    if not args.all:
        cleanup_list = helpers.CONFIG['cleanup']['content_views']

        if not cleanup_list:
            msg = "Cannot find cleanup configuration in config.yml"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(-1)

        msg = "Config found for CV's " + str(cleanup_list)
        helpers.log_msg(msg, 'DEBUG')

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Get the list of Content Views along with the latest view version in each environment
    (ver_list, ver_descr, ver_keep) = get_cv(org_id, cleanup_list, keep)

    # Clean the content views. Returns a list of task IDs.
    cleanup(ver_list, ver_descr, dry_run, runuser, ver_keep)


if __name__ == "__main__":
    main()

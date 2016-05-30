#!/usr/bin/python
#title           :clean_content_views.py
#description     :Cleans orphaned versions of Satellite 6 content views
#URL             :https://github.com/ggatward/sat6_scripts
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Removes unused (orphaned) Content View versions from each environment.
"""

import sys, argparse
import simplejson as json
import helpers


# Get details about Content Views and versions
def get_content_views(org_id, view_name):
    """
    Returns a list of all Content View IDs and Names for a given Org ID
    """
    # Query API to get all content views for our org
    cvlist1 = []
    cvlist2 = []
    cv_list = helpers.get_json(
        helpers.KATELLO_API + "organizations/" + str(org_id) +
        "/content_views/")

    # Only append CV ID's that match the given name
    for cv_results in cv_list['results']:
        cvl = {}
        cvl['id'] = cv_results.get('id')
        cvl['name'] = cv_results.get('name')
        if view_name and cvl['name'] == view_name:
            cvlist1.append(cvl)
        else:
            cvlist2.append(cvl)

    if view_name:
        return cvlist1
    else:
        return cvlist2


def get_content_view_info(cvid):
    """
    Return Content View Info for a given CV ID
    """
    cv_info = helpers.get_json(
        helpers.KATELLO_API + "content_views/" + str(cvid))
    return cv_info


def remove_content_view_version(cv_id, version_id, cv_name):
    """
    Removes Content View version
    Input is the Content View ID and the view version to delete.
    Returns the task ID of the delete job.
    """
    msg = "Removing '" + cv_name + "' (cv_id " + str(cv_id) + ") version_id " + str(version_id)
    helpers.log_msg(msg, 'DEBUG')
    rinfo = helpers.put_json(
        helpers.KATELLO_API + "content_views/" + str(cv_id) + "/remove/",
        json.dumps({
            "id": cv_id,
            "content_view_version_ids": version_id
            }))

    return rinfo


def main():
    """Main Routine"""

    # Who is running this script?
    runuser = helpers.who_is_running()

    # Check for sane input
    parser = argparse.ArgumentParser(description='Removes unused Content Views \
        for specified organization.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization', required=True)
    group.add_argument('-a', '--all', help='Clean ALL views', required=False,
        action="store_true")
    group.add_argument('-v', '--view', help='Name of Content View to clean', required=False)

    args = parser.parse_args()

    # Log the fact we are starting
    msg = "-------- Content View Cleanup started by " + runuser + " -----------"
    helpers.log_msg(msg, 'INFO')

    # Set our script variables from the input args
    org_name = args.org
    view_name = args.view

    if not view_name and not args.all:
        msg = "Content View name not specified, and 'all' was not selected"
        helpers.log_msg(msg, 'WARNING')
        answer = helpers.query_yes_no("Proceed to clean ALL Content Views?", "no")
        if not answer:
            msg = "Cleanup aborted by user"
            helpers.log_msg(msg, 'INFO')
            sys.exit(-1)


    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Get the list of content views
    cvlist = get_content_views(org_id, view_name)

    # Log what we are doing
    if view_name:
        msg = "Cleaning content view " + view_name
    else:
        msg = "Cleaning all content views"
    helpers.log_msg(msg, 'DEBUG')

    # Run the cleanup
    if cvlist:
        for cv_results in cvlist:
            # We need to find all versions of each affected content view
            cvinfo = get_content_view_info(cv_results['id'])
            for version in cvinfo['versions']:
                if not version['environment_ids']:
                    # Delete the view version from the content view
                    cvrtask = remove_content_view_version(
                        cv_results['id'], version['id'], cv_results['name']
                        )

                    # Wait for it to complete
                    helpers.wait_for_task(cvrtask['id'])

                    # Check if the deletion completed successfully
                    tinfo = helpers.get_task_status(cvrtask['id'])
                    if tinfo['state'] != 'running' and tinfo['result'] == 'success':
                        msg = "Removal of content view version ID=" + str(version['id']) + " OK"
                        helpers.log_msg(msg, 'INFO')
                        print msg
                    else:
                        msg = "Removal of content view version ID=" + str(version['id']) + " failed"
                        helpers.log_msg(msg, 'ERROR')
    else:
        # Unable to get CV list, or specific view not found
        msg = "Content view not found"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(1)


if __name__ == "__main__":
    main()

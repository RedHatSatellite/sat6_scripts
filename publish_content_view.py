#!/usr/bin/python
#title           :publish_content_view.py
#description     :Publishes new versions of Satellite 6 content views
#URL             :https://github.com/ggatward/sat6_scripts
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Publishes new content view versions to the Library

"""
#pylint: disable-msg=R0912,R0913,R0914,R0915

import sys, argparse
import simplejson as json
import helpers


def get_cv(org_id, publish_list, exclude_list):
    """Get the content views"""

    if publish_list:
        pubstring = ', '.join(str(e) for e in publish_list)
        msg = "Publishing only specified content view '" + pubstring + "'"
        helpers.log_msg(msg, 'DEBUG')

    if exclude_list:
        exstring = ', '.join(str(e) for e in exclude_list)
        msg = "Publishing all content views except '" + exstring + "'"
        helpers.log_msg(msg, 'DEBUG')


    # Query API to get all content views for our org
    cvs = helpers.get_json(
        helpers.KATELLO_API + "organizations/" + str(org_id) + "/content_views/")
    ver_list = {}
    ver_descr = {}
    ver_version = {}

    for cv_result in cvs['results']:
        # We will never publish the DOV
        if cv_result['name'] != "Default Organization View":

            # Handle specific includes and excludes
            if publish_list and cv_result['name'] not in publish_list:
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
            ver_version[cv_result['id']] = cv_result['next_version']

    return ver_list, ver_descr, ver_version


def publish(ver_list, ver_descr, ver_version, dry_run, runuser):
    """Publish Content View"""

    # Set the task name to be displayed in the task monitoring stage
    task_name = "Publish content view to Library"

    # Now we have all the info needed, we can actually trigger the publish.
    task_list = []
    ref_list = {}

    # Catch scenario that no CV versions are found matching publish criteria
    if not ver_list:
        msg = "No content view versions found matching publication criteria"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    for cvid in ver_list.keys():

        # Check if there is a publish/promote already running on this content view
        locked = helpers.check_running_publish(ver_list[cvid], ver_descr[cvid])

        if not locked:
            msg = "Publishing '" + str(ver_descr[cvid]) + "' Version " + str(ver_version[cvid]) + ".0"
            helpers.log_msg(msg, 'INFO')
            print helpers.HEADER + msg + helpers.ENDC

        # Set up the description that will be added to the published version
        description = "Published by " + runuser + "\n via API script"

        if not dry_run and not locked:
            try:
                task_id = helpers.post_json(
                    helpers.KATELLO_API + "content_views/" + str(ver_list[cvid]) +\
                    "/publish", json.dumps(
                        {
                            "description": description
                        }
                        ))["id"]
            except Warning:
                msg = "Failed to initiate publication of " + str(ver_descr[cvid])
                helpers.log_msg(msg, 'WARNING')
            else:
                task_list.append(task_id)
                ref_list[task_id] = ver_descr[cvid]

    # Exit in the case of a dry-run
    if dry_run:
        msg = "Dry run - not actually performing publish"
        helpers.log_msg(msg, 'WARNING')
        sys.exit(-1)


    return task_list, ref_list, task_name


def main():
    """
    Main routine
    """

    # Who is running this script?
    runuser = helpers.who_is_running()

    # Check for sane input
    parser = argparse.ArgumentParser(
        description='Publishes content views for specified organization.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization', required=True)
    group.add_argument('-x', '--exfile',
        help='Publish all content views EXCEPT those listed in file', required=False)
    group.add_argument('-i', '--infile', help='Publish only content views listed in file',
        required=False)
    group.add_argument('-a', '--all', help='Publish ALL content views', required=False,
        action="store_true")
    parser.add_argument('-d', '--dryrun', help='Dry Run - Only show what will be published',
        required=False, action="store_true")

    args = parser.parse_args()

    # Log the fact we are starting
    msg = "-------- Content view publish started by " + runuser + " -----------"
    helpers.log_msg(msg, 'INFO')

    # Set our script variables from the input args
    org_name = args.org
    dry_run = args.dryrun
    publish_file = args.infile
    exclude_file = args.exfile

    if not exclude_file and not publish_file and not args.all:
        msg = "Content view to publish not specified, and 'all' was not selected"
        helpers.log_msg(msg, 'WARNING')
        answer = helpers.query_yes_no("Proceed to publish ALL content views?", "no")
        if not answer:
            msg = "Publish aborted by user"
            helpers.log_msg(msg, 'INFO')
            sys.exit(-1)

    # Read in the exclusion file to the exclude list
    exclude_list = []
    publish_list = []
    if exclude_file or publish_file:
        try:
            if exclude_file:
                xfile = open(exclude_file, 'r')
                exclude_list = [line.rstrip('\n') for line in xfile]
            if publish_file:
                xfile = open(publish_file, 'r')
                publish_list = [line.rstrip('\n') for line in xfile]
        except IOError:
            msg = "Cannot find input file"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(-1)

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Get the list of Content Views along with the latest view version in each environment
    (ver_list, ver_descr, ver_version) = get_cv(org_id, publish_list, exclude_list)

    # Publish the content views. Returns a list of task IDs.
    (task_list, ref_list, task_name) = publish(ver_list, ver_descr, ver_version, dry_run, runuser)

    # Monitor the status of the publish tasks
    helpers.watch_tasks(task_list, ref_list, task_name)


if __name__ == "__main__":
    main()

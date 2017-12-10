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

import sys
import os
import argparse
import datetime
import pickle
import simplejson as json
import helpers


def get_cv(org_id, publish_list):
    """Get the content views"""

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

            # Get the ID of each Content View
            msg = "Processing content view '" + cv_result['name'] + "' " + str(cv_result['id'])
            helpers.log_msg(msg, 'DEBUG')

            # Find the next version of the view
            ver_list[cv_result['id']] = cv_result['id']
            ver_descr[cv_result['id']] = cv_result['name']
            ver_version[cv_result['id']] = cv_result['next_version']

    return ver_list, ver_descr, ver_version


def publish(ver_list, ver_descr, ver_version, dry_run, runuser, quiet):
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
        if helpers.MAILOUT:
            helpers.tf.seek(0)
            output = "{}".format(helpers.tf.read())
            helpers.mailout(helpers.MAILSUBJ_FP, output)
        sys.exit(1)

    # Break repos to publish into batches as configured in config.yml
    cvchunks = [ ver_list.keys()[i:i+helpers.PUBLISHBATCH] for i in range(0, len(ver_list), helpers.PUBLISHBATCH) ]

    # Loop through the smaller subsets of repo id's
    for chunk in cvchunks:
        for cvid in chunk:

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

        # Notify user in the case of a dry-run
        if dry_run:
            msg = "Dry run - not actually performing publish"
            helpers.log_msg(msg, 'WARNING')
        else:
            # Wait for the tasks to finish
            helpers.watch_tasks(task_list, ref_list, task_name, quiet)

    # Exit in the case of a dry-run
    if dry_run:
        sys.exit(2)
    else:
        return


def main(args):
    """
    Main routine
    """

    # Who is running this script?
    runuser = helpers.who_is_running()

    # Set the base dir of the script and where the var data is
    global dir
    global vardir
    dir = os.path.dirname(__file__)
    vardir = os.path.join(dir, 'var')
    confdir = os.path.join(dir, 'config')

    # Check for sane input
    parser = argparse.ArgumentParser(
        description='Publishes content views for specified organization.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization (Uses default if not specified)',
        required=False)
    group.add_argument('-a', '--all', help='Publish ALL content views', required=False,
        action="store_true")
    parser.add_argument('-d', '--dryrun', help='Dry Run - Only show what will be published',
        required=False, action="store_true")
    parser.add_argument('-l', '--last', help='Display last promotions', required=False,
        action="store_true")
    parser.add_argument('-q', '--quiet', help="Suppress progress output updates", required=False,
        action="store_true")

    args = parser.parse_args()

    # Log the fact we are starting
    if not args.last:
        msg = "-------- Content view publish started by " + runuser + " -----------"
        helpers.log_msg(msg, 'INFO')

    # Set our script variables from the input args
    if args.org:
        org_name = args.org
    else:
       org_name = helpers.ORG_NAME
    dry_run = args.dryrun

    # Load the promotion history
    if not os.path.exists(vardir + '/promotions.pkl'):
        if not os.path.exists(vardir):
            os.makedirs(vardir)
        phistory = {}
    else:
        phistory = pickle.load(open(vardir + '/promotions.pkl', 'rb'))

    # Read the promotion history if --last requested
    if args.last:
        if phistory:
            print 'Last promotions:'
            for lenv, time in phistory.iteritems():
                print lenv, time
        else:
            print 'No promotions recorded'
        sys.exit(0)


    publish_list = []
    if not args.all:
        publish_list = helpers.CONFIG['publish']['content_views']

        if not publish_list:
            msg = "Cannot find publish configuration"
            helpers.log_msg(msg, 'ERROR')
            if helpers.MAILOUT:
                helpers.tf.seek(0)
                output = "{}".format(helpers.tf.read())
                helpers.mailout(helpers.MAILSUBJ_FP, output)
            sys.exit(1)

        msg = "Config found for CV's " + str(publish_list)
        helpers.log_msg(msg, 'DEBUG')

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Get the list of Content Views along with the latest view version in each environment
    (ver_list, ver_descr, ver_version) = get_cv(org_id, publish_list)

    # Publish the content views. Returns a list of task IDs.
    publish(ver_list, ver_descr, ver_version, dry_run, runuser, args.quiet)

    # Add/Update the promotion history dictionary so we can check when we last promoted
    phistory['Library'] = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d')
    pickle.dump(phistory, open(vardir + '/promotions.pkl', 'wb'))

    # Run the mailout
    if helpers.MAILOUT:
        helpers.tf.seek(0)
        output = "{}".format(helpers.tf.read())
        message = "Publish completed successfully\n\n" + output
        subject = "Satellite 6 publish completed"
        helpers.mailout(subject, message)

    # Exit cleanly
    sys.exit(0)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        print >> sys.stderr, ("\n\nExiting on user cancel.")
        sys.exit(1)

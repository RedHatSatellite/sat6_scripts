#!/usr/bin/python
#title           :promote_content_view.py
#description     :Promotes Satellite 6 content view versions
#URL             :https://github.com/ggatward/sat6_scripts
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Promotes Content Views from the previous lifecycle environment.

"""
#pylint: disable-msg=R0912,R0913,R0914,R0915

import sys
import os
import argparse
import datetime
import pickle
import simplejson as json
import helpers

try:
    import yaml
except ImportError:
    print "Please install the PyYAML module."
    sys.exit(1)


# Get the details about the environments
def get_envs(org_id):
    """Get list of environments for the given org"""
    envs = helpers.get_json(
        helpers.SAT_API + "organizations/" + str(org_id) + "/environments/")

    # ... and add them to a dictionary, with respective 'Prior' environment
    env_list = {}
    prior_list = {}
    for env in envs['results']:
        env_list[env['name']] = env['id']
        if env['name'] == "Library":
            prior = 0
        else:
            prior = env['prior']['id']
        prior_list[env['id']] = prior

        msg = "Found environment '" + env['name'] + "', env_id " + str(env['id']) +\
            " (prior_id " + str(prior) + ")"
        helpers.log_msg(msg, 'DEBUG')

    return env_list, prior_list


# Get details about Content Views and versions
def get_cv(org_id, target_env, env_list, prior_list, promote_list):
    """Get the content views"""
    # Find the ID of the environment we are promoting to and from
    if not target_env in env_list:
        msg = "Target environment '" + target_env + "' not found"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(1)
    else:
        target_env_id = env_list[target_env]
        source_env_id = prior_list[target_env_id]

    # Query API to get all content views for our org
    cvs = helpers.get_json(
        helpers.KATELLO_API + "organizations/" + str(org_id) + "/content_views/")
    ver_list = {}
    ver_descr = {}
    ver_version = {}

    for cv_result in cvs['results']:
        # We will never promote to/from the DOV
        if cv_result['name'] != "Default Organization View":

            # Handle specific includes and excludes
            if promote_list and cv_result['name'] not in promote_list:
                msg = "Skipping content view '" + cv_result['name'] + "'"
                helpers.log_msg(msg, 'DEBUG')
                continue

            # Get the ID of each Content View
            msg = "Processing content view '" + cv_result['name'] + "'"
            helpers.log_msg(msg, 'DEBUG')

            # Find the current version of the view in the env we are coming from
            for ver in cv_result['versions']:
                msg = "  Found in env_id " + str(ver['environment_ids']) + " view_id " +\
                    str(ver['id'])
                helpers.log_msg(msg, 'DEBUG')

                if source_env_id in ver['environment_ids']:
                    # Extract the name of the source environment so we can inform the user
                    for key, val in env_list.items():
                        if val == source_env_id:
                            prior_env = key
                    msg = "Found promotable version " + ver['version'] + " of '" +\
                        cv_result['name'] + "' in " + prior_env
                    helpers.log_msg(msg, 'INFO')
                    print msg

                    # Create a dictionary of CV IDs and the CV vers ID to promote
                    ver_list[cv_result['id']] = ver['id']
                    ver_descr[cv_result['id']] = cv_result['name']
                    ver_version[cv_result['id']] = ver['version']

    return ver_list, ver_descr, ver_version


# Promote a content view version
def promote(target_env, ver_list, ver_descr, ver_version, env_list, prior_list, dry_run):
    """Promote Content View"""
    target_env_id = env_list[target_env]
    source_env_id = prior_list[target_env_id]

    # Extract the name of the source environment so we can inform the user
    for key, val in env_list.items():
        if val == source_env_id:
            prior_env = key

    # Set the task name to be displayed in the task monitoring stage
    task_name = "Promotion from " + prior_env + " to " + target_env

    # Now we have all the info needed, we can actually trigger the promotion.
    # Loop through each CV with promotable versions
    task_list = []
    ref_list = {}

    # Catch scenario that no CV versions are found matching promotion criteria
    if not ver_list:
        msg = "No content view versions found matching promotion criteria"
        helpers.log_msg(msg, 'WARNING')
        sys.exit(1)

    for cvid in ver_list.keys():

        # Check if there is a publish/promote already running on this content view
        locked = helpers.check_running_publish(cvid, ver_descr[cvid])

        if not locked:
            msg = "Promoting '" + str(ver_descr[cvid]) + "' Version " + str(ver_version[cvid]) +\
                " from " + prior_env + " to " + str(target_env)
            helpers.log_msg(msg, 'INFO')
            print helpers.HEADER + msg + helpers.ENDC

        if not dry_run and not locked:
            try:
                task_id = helpers.post_json(
                    helpers.KATELLO_API + "content_view_versions/" + str(ver_list[cvid]) +\
                    "/promote/", json.dumps(
                        {
                            "environment_id": target_env_id
                        }
                        ))["id"]
            except Warning:
                msg = "Failed to initiate promotion of " + str(ver_descr[cvid])
                helpers.log_msg(msg, 'WARNING')
            else:
                task_list.append(task_id)
                ref_list[task_id] = ver_descr[cvid]

    # Exit in the case of a dry-run
    if dry_run:
        msg = "Dry run - not actually performing promotion"
        helpers.log_msg(msg, 'WARNING')
        sys.exit(2)


    return task_list, ref_list, task_name


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
#    confdir = os.path.join(dir, 'config')

    # Check for sane input
    parser = argparse.ArgumentParser(
        description='Promotes content views for specified organization to the target environment.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-e', '--env', help='Target Environment (e.g. Development, Quality, Production)',
        required=False)
    parser.add_argument('-o', '--org', help='Organization (Uses default if not specified)',
        required=False)
    group.add_argument('-a', '--all', help='Promote ALL content views', required=False,
        action="store_true")
    parser.add_argument('-d', '--dryrun', help='Dry Run - Only show what will be promoted',
        required=False, action="store_true")
    parser.add_argument('-l', '--last', help='Display last promotions', required=False,
        action="store_true")
    parser.add_argument('-q', '--quiet', help="Suppress progress output updates", required=False,
        action="store_true")

    args = parser.parse_args()

    # Log the fact we are starting
    msg = "-------- Content view promotion started by " + runuser + " -----------"
    helpers.log_msg(msg, 'INFO')

    # Set our script variables from the input args
    if args.org:
        org_name = args.org
    else:
       org_name = helpers.ORG_NAME
    target_env = args.env
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

    # Error if no environment to promote to is given
    if args.env is None:
        parser.error('--env is required')

    promote_list = []
    if not args.all:
        for x in helpers.CONFIG['promotion']:
            if helpers.CONFIG['promotion'][x]['name'] == target_env:
                promote_list = helpers.CONFIG['promotion'][x]['content_views']

        if not promote_list:
            msg = "Cannot find promotion configuration for '" + target_env + "'"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(1)

        msg = "Config found for CV's " + str(promote_list)
        helpers.log_msg(msg, 'DEBUG')

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Now, let's fetch all available lifecycle environments for this org...
    (env_list, prior_list) = get_envs(org_id)

    # Get the list of Content Views along with the latest view version in each environment
    (ver_list, ver_descr, ver_version) = get_cv(org_id, target_env, env_list, prior_list,
        promote_list)

    # Promote to the given environment. Returns a list of task IDs.
    (task_list, ref_list, task_name) = promote(target_env, ver_list, ver_descr, ver_version,
        env_list, prior_list, dry_run)

    # Add/Update the promotion history dictionary so we can check when we last promoted
    phistory[target_env] = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d')
    pickle.dump(phistory, open(vardir + '/promotions.pkl', 'wb'))

    # Monitor the status of the promotion tasks
    helpers.watch_tasks(task_list, ref_list, task_name, args.quiet)

    # Exit cleanly
    sys.exit(0)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        print >> sys.stderr, ("\n\nExiting on user cancel.")
        sys.exit(1)

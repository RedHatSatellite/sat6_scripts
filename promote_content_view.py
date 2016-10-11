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

import sys, argparse
import simplejson as json
import helpers


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
def get_cv(org_id, target_env, env_list, prior_list, promote_list, exclude_list):
    """Get the content views"""
    # Find the ID of the environment we are promoting to and from
    if not target_env in env_list:
        msg = "Target environment '" + target_env + "' not found"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)
    else:
        target_env_id = env_list[target_env]
        source_env_id = prior_list[target_env_id]

    if promote_list:
        prostring = ', '.join(str(e) for e in promote_list)
        msg = "Promoting only specified content view '" + prostring + "'"
        helpers.log_msg(msg, 'DEBUG')

    if exclude_list:
        exstring = ', '.join(str(e) for e in exclude_list)
        msg = "Promoting all views except '" + exstring + "'"
        helpers.log_msg(msg, 'DEBUG')


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

            if exclude_list and cv_result['name'] in exclude_list:
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
        sys.exit(-1)

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
        description='Promotes content views for specified organization to the target environment.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-e', '--env', help='Target Environment (e.g. Development, Quality, Production)',
        required=True)
    parser.add_argument('-o', '--org', help='Organization', required=True)
    group.add_argument('-x', '--exfile',
        help='Promote all content views EXCEPT those listed in file', required=False)
    group.add_argument('-i', '--infile', help='Promote only content views listed in file',
        required=False)
    group.add_argument('-a', '--all', help='Promote ALL content views', required=False,
        action="store_true")
    parser.add_argument('-d', '--dryrun', help='Dry Run - Only show what will be promoted',
        required=False, action="store_true")

    args = parser.parse_args()

    # Log the fact we are starting
    msg = "-------- Content view promotion started by " + runuser + " -----------"
    helpers.log_msg(msg, 'INFO')

    # Set our script variables from the input args
    org_name = args.org
    target_env = args.env
    dry_run = args.dryrun
    promote_file = args.infile
    exclude_file = args.exfile

    if not exclude_file and not promote_file and not args.all:
        msg = "Content view to promote/exclude not specified, and 'all' was not selected"
        helpers.log_msg(msg, 'WARNING')
        answer = helpers.query_yes_no("Proceed to promote ALL content views?", "no")
        if not answer:
            msg = "Promotion aborted by user"
            helpers.log_msg(msg, 'INFO')
            sys.exit(-1)

    # Read in the exclusion file to the exclude list
    exclude_list = []
    promote_list = []
    if exclude_file or promote_file:
        try:
            if exclude_file:
                xfile = open(exclude_file, 'r')
                exclude_list = [line.rstrip('\n') for line in xfile]
            if promote_file:
                xfile = open(promote_file, 'r')
                promote_list = [line.rstrip('\n') for line in xfile]
        except IOError:
            msg = "Cannot find input file"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(-1)

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Now, let's fetch all available lifecycle environments for this org...
    (env_list, prior_list) = get_envs(org_id)

    # Get the list of Content Views along with the latest view version in each environment
    (ver_list, ver_descr, ver_version) = get_cv(org_id, target_env, env_list, prior_list,
        promote_list, exclude_list)

    # Promote to the given environment. Returns a list of task IDs.
    (task_list, ref_list, task_name) = promote(target_env, ver_list, ver_descr, ver_version,
        env_list, prior_list, dry_run)

    # Monitor the status of the promotion tasks
    helpers.watch_tasks(task_list, ref_list, task_name)


if __name__ == "__main__":
    main()


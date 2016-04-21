#!/usr/bin/python
"""
Promotes Content Views from the previous lifecycle environment.

NOTE:  This file is managed by the STASH git repository. Any modifications to
       this file must be made in the source repository and then deployed.
"""

import sys, argparse
import simplejson as json
import sat6functions, config
import logging

DEBUG = 0

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(message)s',
                    datefmt='%b %d %H:%M:%S',
                    filename=config.LOGFILE,
                    filemode='w')

#-----------------------

def log_message(msg, level):
    """Write a log message"""
    # Everything is written to file:
    logging.info(level + " " + msg)
    # But we only output non-debug to stdout unless debug is set
    if not DEBUG:
        if level != 'DEBUG':
            print msg
    else:
        print msg

# Get the details about the environments
def get_envs(org_id):
    """Get list of environments for the given org"""
    envs = sat6functions.get_json(
        sat6functions.SAT_API + "organizations/" + str(org_id) + "/environments/")

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

        msg = "Env Name:     %s" % env['name']
        log_message(msg, 'DEBUG')
        msg = "Env ID:       %s" % env['id']
        log_message(msg, 'DEBUG')
        msg = "Prior Env ID: %s" % prior
        log_message(msg, 'DEBUG')

    return env_list, prior_list


# Get details about Content Views and versions
def get_cv(org_id, target_env, env_list, prior_list):
    """Get the content views"""
    # Find the ID of the environment we are promoting to and from
    target_env_id = env_list[target_env]
    source_env_id = prior_list[target_env_id]

    msg = "From Env ID: %s" % source_env_id
    log_message(msg, 'DEBUG')
    msg = "To Env ID:   %s" % target_env_id
    log_message(msg, 'DEBUG')

    # Query API to get all content views for our org
    cvs = sat6functions.get_json(
        sat6functions.KATELLO_API + "organizations/" + str(org_id) + "/content_views/")
    ver_list = {}
    ver_descr = {}
    for cv_result in cvs['results']:
        if cv_result['name'] != "Default Organization View" \
        and cv_result['name'] != "Server SOE" and cv_result['name'] != "Puppet Test"\
        and cv_result['name'] != "Workstation SOE":
            # Get the ID of each Content View
            print "CV: " + cv_result['name']

            # Find the current version of the view in the env we are coming from
            for ver in cv_result['versions']:
                msg = "  Env ID:     " + str(ver['environment_ids'])
                log_message(msg, 'DEBUG')
                msg = "  Version:    " + str(ver['version'])
                log_message(msg, 'DEBUG')
                msg = "  Version ID: " + str(ver['id'])
                log_message(msg, 'DEBUG')

                if source_env_id in ver['environment_ids']:
                    print "    * Found promotable version " + ver['version'] +\
                    " in environment ID " + str(source_env_id)
                    # Create a dictionary of CV IDs and the CV vers ID to promote from previous ver
                    ver_list[cv_result['id']] = ver['id']
                    ver_descr[cv_result['id']] = cv_result['name']

    return ver_list, ver_descr


# Promote a content view version
def promote(target_env, ver_list, ver_descr, env_list, prior_list):
    """Promote Content View"""
    target_env_id = env_list[target_env]
    source_env_id = prior_list[target_env_id]

    msg = "Promoting to Env %s (ID %s) From ID %s" % (target_env, target_env_id, source_env_id)
    log_message(msg, 'DEBUG')

    # Now we have all the info needed, we can actually trigger the promotion.
    # Loop through each CV with promotable versions
    task_list = []
    ref_list = {}
    for cvid in ver_list.keys():
        print "Promoting CV_ID=" + str(cvid) + " (" + str(ver_descr[cvid]) + ") version ID=" +\
        str(ver_list[cvid]) + " from env ID=" + str(source_env_id) + " to " + str(target_env)

        try:
            task_id = sat6functions.post_json(
                sat6functions.KATELLO_API + "content_view_versions/" + str(ver_list[cvid]) +\
                "/promote/", json.dumps(
                    {
                        "environment_id": target_env_id
                    }
                    ))["id"]
        except Warning:
            print "WARNING: Failed to initiate promotion\n"
        else:
            task_list.append(task_id)
            ref_list[task_id] = ver_descr[cvid]

    return task_list, ref_list


def main():
    """
    Main routine
    """
    # Check for sane input
    parser = argparse.ArgumentParser(description='Promotes all content views for specified organization to the target environment.')
    parser.add_argument('-e', '--env', help='Target Environment (Development, Quality, Production)', required=True)
    parser.add_argument('-o', '--org', help='Organization', required=True)
    args = parser.parse_args()

    # Set our script variables from the input args
    org_name = args.org
    target_env = args.env

    if target_env == "Development" or target_env == "Quality" or target_env == "Production":
        print "Info: Will promote to " + target_env
    else:
        sys.stderr.write("Error: Invalid environment specified. Correct values are Development | Quality | Production\n")
        sys.exit(1)


    # Check if our organization exists, and extract its ID
    org = sat6functions.get_json(sat6functions.SAT_API + "organizations/" + org_name)
    # If our organization is not found, exit
    if org.get('error', None):
        print "Organization '%s' does not exist." % org_name
        sys.exit(-1)
    else:
        # Our organization exists, so let's grab the ID
        org_id = org['id']

    # Now, let's fetch all available lifecycle environments for this org...
    (env_list, prior_list) = get_envs(org_id)

    # Get the list of Content Views along with the latest view version in each environment
    (ver_list, ver_descr) = get_cv(org_id, target_env, env_list, prior_list)

    # Promote to the given environment. Returns a list of task IDs.
    (task_list, ref_list) = promote(target_env, ver_list, ver_descr, env_list, prior_list)

    # Monitor the status of the promotion tasks
    sat6functions.watch_tasks(task_list, ref_list)


if __name__ == "__main__":
    main()

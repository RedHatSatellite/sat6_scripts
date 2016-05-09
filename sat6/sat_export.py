#!/usr/bin/python
"""
Exports Default Org Content View.

NOTE:  This file is managed by the STASH git repository. Any modifications to
       this file must be made in the source repository and then deployed.
"""

import sys, argparse, datetime, os, shutil
import glob, fnmatch, subprocess, tarfile
import simplejson as json
from time import sleep
import helpers

# Get details about Content Views and versions
def get_cv(org_id):
    """
    Get the version of the Content Views
    There should only ever be ONE version of the Default Org View.
    It Should be v1.0 with id=1, but we're verifying here just in case.
    """

    # Query API to get all content views for our org
    cvs = helpers.get_json(
        helpers.KATELLO_API + "organizations/" + str(org_id) + "/content_views/")
    ver_list = {}
    ver_descr = {}
    for cv_result in cvs['results']:
        if cv_result['name'] == "Default Organization View":
            msg = "CV Name: " + cv_result['name']
            helpers.log_msg(msg, 'DEBUG')

            # Find the current version of the view in the env we are coming from
            for ver in cv_result['versions']:
                msg = "  Env ID:     " + str(ver['environment_ids'])
                helpers.log_msg(msg, 'DEBUG')
                msg = "  Version:    " + str(ver['version'])
                helpers.log_msg(msg, 'DEBUG')
                msg = "  Version ID: " + str(ver['id'])
                helpers.log_msg(msg, 'DEBUG')

        # There will only ever be one DOV
        return cv_result['id']


# Promote a content view version
def export_cv(dov_ver, last_export):
    """
    Export Content View
    Takes the content view version and a start time (API 'since' value)
    """

    msg = "Exporting DOV version " + str(dov_ver) + " from start date " + last_export
    helpers.log_msg(msg, 'INFO')

    # /katello/api/content_view_versions/:id/export
    try:
        task_id = helpers.post_json(
            helpers.KATELLO_API + "content_view_versions/" + str(dov_ver) + "/export/", \
                json.dumps(
                {
                    "since": last_export,
                }
                ))["id"]
    except:
        msg = "Unable to start export - Export already in progress"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    # Trap some other error conditions
    if "Required lock is already taken" in str(task_id):
        msg = "Unable to start export - Sync in progress"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    msg = "Export started, task_id = " + str(task_id)
    helpers.log_msg(msg, 'DEBUG')

    return str(task_id)


def check_running_tasks():
    """
    Check for any currently running Sync or Export tasks
    Exits script if any Synchronize or Export tasks are found in a running state.
    """
    tasks = helpers.get_json(
        helpers.FOREMAN_API + "tasks/")
    
    # From the list of tasks, look for any running export or sync jobs.
    # If e have any we exit, as we can't export in this state.
    for task_result in tasks['results']:
        if task_result['state'] == 'running':
            if task_result['humanized']['action'] == 'Export':
                msg = "Unable to export - an Export task is already running"
                helpers.log_msg(msg, 'ERROR')
                sys.exit(-1)
            if task_result['humanized']['action'] == 'Synchronize':
                msg = "Unable to export - a Sync task is currently running"
                helpers.log_msg(msg, 'ERROR')
                sys.exit(-1)
        

def locate(pattern, root=os.curdir):
    for path, dirs, files in os.walk(os.path.abspath(root)):
        for filename in fnmatch.filter(files, pattern):
            yield os.path.join(path, filename)


def do_gpg_check(export_dir):
    """
    Find and GPG Check all RPM files
    """
    export_path = helpers.EXPORTDIR + "/" + export_dir
    msg = "Checking GPG integrity of RPMs in " + export_path
    helpers.log_msg(msg, 'INFO')
    print msg

    badrpms = []
    os.chdir(export_path)
    for rpm in locate("*.rpm"):
        return_code = subprocess.call("rpm -K " + rpm, shell=True, stdout=open(os.devnull, 'wb'))

        # A non-zero return code indicates a GPG check failure.
        if return_code != 0:
            # For display purposes, strip the first 6 directory elements
            rpmnew = os.path.join(*(rpm.split(os.path.sep)[6:]))
            badrpms.append(rpmnew)

    # If we have any bad ones we need to fail the export.
    if len(badrpms) != 0:
        msg = "The following RPM's failed the GPG check.."
        helpers.log_msg(msg, 'ERROR')
        for badone in badrpms:
            msg = badone
            helpers.log_msg(msg, 'ERROR')
        msg = "------ Export Aborted ------"
        helpers.log_msg(msg, 'ERROR')
#        sys.exit(-1)
  

def create_tar(export_dir):
    """
    Create a TAR of the content we have exported
    """
    export_path = helpers.EXPORTDIR + "/" + export_dir
    msg = "Creating TAR file"
    helpers.log_msg(msg, 'INFO')
    print msg

    os.chdir(export_path)
    with tarfile.open(helpers.EXPORTDIR + "/content_export" + '.tar', 'w') as archive:
        archive.add(os.curdir, recursive=True)


def write_timestamp(start_time):
    """
    Append the start timestamp to our export record
    """
    f = open('../var/exports.dat','a')
    f.write(start_time + "\n")
    f.close()


def read_timestamp():
    """
    Read the last successful export timestamp from our export record file
    """
    with open('../var/exports.dat','r') as f:
        last = None
        for line in (line for line in f if line.rstrip('\n')):
            last = line.rstrip('\n')
    return last


def main():
    """
    Main Routine
    """
    # Log the fact we are starting
    msg = "------------- Content export started by ..user.. ----------------"
    helpers.log_msg(msg, 'INFO')

    # Check for sane input
    parser = argparse.ArgumentParser(description='Performs Export of Default Content View.')
    group = parser.add_mutually_exclusive_group()
    parser.add_argument('-o', '--org', help='Organization', required=True)
    group.add_argument('-a', '--all', help='Export ALL content', required=False, action="store_true")
    group.add_argument('-i', '--incr', help='Incremental Export of content since last run', required=False, action="store_true")
    group.add_argument('-s', '--since', help='Export content since YYYY-MM-DD HH:MM:SS', required=False, type=helpers.valid_date)
    parser.add_argument('-l', '--last', help='Display time of last export', required=False, action="store_true")
    args = parser.parse_args()


    # Set our script variables from the input args
    org_name = args.org
    since = args.since

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Get the current time - this will be the 'last export' time if the export is OK
    start_time = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')
    print "START: " + start_time

    # Get the last export date. If we're exporting all, this isn't relevant
    # If we are given a start date, use that, otherwise we need to get the last date from file
    if not args.all:
        if not since:
            last_export = read_timestamp()
            if args.last:
                print "Last successful export was started at " + last_export
                sys.exit(-1)
        else:
            last_export = str(since)
     
        # We have our timestamp so we can kick of an incremental export
        print "Incremental export of content synchronised after " + last_export
    else:
        print "Full export of content"

    # TODO 
    # Remove any previous exported content
#    os.chdir(helpers.EXPORTDIR)
#    shutil.rmtree()

    # Get the version of the CV (Default Org View) to export
    dov_ver = get_cv(org_id)

    # Check if there are any currently running tasks that will conflict with an export
    check_running_tasks()

    # Now we have a CV ID and a starting date, and no conflicting tasks, we can export
    export_id = export_cv(dov_ver, last_export)

    # Now we need to wait for the export to complete
    helpers.wait_for_task(export_id)

    # Check if the export completed OK. If not we exit the script.
    tinfo = helpers.get_task_status(export_id)
    if tinfo['state'] != 'running' and tinfo['result'] == 'success':
        msg = "Content View Export OK"
        helpers.log_msg(msg, 'INFO')
        print msg
    else:
        msg = "Content View Export FAILED"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    # Now we need to process the on-disk export data
    # Find the name of our export dir. This ASSUMES that the export dir is the ONLY dir.
    sat_export_dir = os.listdir(helpers.EXPORTDIR)
    export_dir = sat_export_dir[0]
    
    # Run GPG Checks on the exported RPMs
    do_gpg_check(export_dir)

    # Add our exported data to a tarfile
    create_tar(export_dir)


    # We're done. Write the start timestamp to file for next time
#    write_timestamp(start_time)


if __name__ == "__main__":
    main()


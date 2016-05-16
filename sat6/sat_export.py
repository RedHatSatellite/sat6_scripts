#!/usr/bin/python
#title           :sat_export.py
#description     :Exports Satellite 6 Default Content View for disconnected environments
#URL             :https://github.com/ggatward/sat6_scripts
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Exports Default Org Content View.
"""

import sys, argparse, datetime, os, shutil
import fnmatch, subprocess, tarfile
import simplejson as json
from glob import glob
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

    try:
        task_id = helpers.post_json(
            helpers.KATELLO_API + "content_view_versions/" + str(dov_ver) + "/export/", \
                json.dumps(
                    {
                        "since": last_export,
                    }
                ))["id"]
    except: # pylint: disable-msg=W0702
        msg = "Unable to start export - Conflicting Sync or Export already in progress"
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
        if task_result['state'] == 'paused':
            if task_result['humanized']['action'] == 'Export':
                msg = "Unable to export - an Export task is paused. Please resolve this issue first"
                helpers.log_msg(msg, 'ERROR')
                sys.exit(-1)
            if task_result['humanized']['action'] == 'Synchronize':
                msg = "Unable to export - a Sync task is paused. Resume any paused sync tasks."
                helpers.log_msg(msg, 'ERROR')
                sys.exit(-1)

        # TODO: Check for other incomplete-sync status tasks.
        # All need to be complete to ensure consistent sync

def check_disk_space(export_type):
    """
    Check the disk usage of the pulp partition
    For a full export we need at least 50% free, as we spool to /var/lib/pulp.
    """
    pulp_used = str(helpers.disk_usage('/var/lib/pulp'))
    if export_type == 'full' and pulp_used > '50':
        msg = "Insufficient space in /var/lib/pulp for a full export. >50% free space is required."
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)


def locate(pattern, root=os.curdir):
    """Provides simple 'locate' functionality for file search"""
    # pylint: disable=unused-variable
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
        sys.exit(-1)
    else:
        msg = "GPG check completed successfully"
        helpers.log_msg(msg, 'INFO')
        print helpers.GREEN + "GPG Check - Pass" + helpers.ENDC


def create_tar(export_dir):
    """
    Create a TAR of the content we have exported
    Creates a single tar, then splits into DVD size chunks and calculates
    sha256sum for each chunk.
    """
    export_path = helpers.EXPORTDIR + "/" + export_dir
    today = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d')
    msg = "Creating TAR files..."
    helpers.log_msg(msg, 'INFO')
    print msg

    os.chdir(export_path)
    full_tarfile = helpers.EXPORTDIR + '/sat6_export_' + today
    short_tarfile = 'sat6_export_' + today
    with tarfile.open(full_tarfile, 'w') as archive:
        archive.add(os.curdir, recursive=True)

    # Get a list of all the RPM content we are exporting
    result = [y for x in os.walk(export_path) for y in glob(os.path.join(x[0], '*.rpm'))]
    if result:
        f_handle = open(helpers.LOGDIR + '/export_' + today + '.log', 'a+')
        f_handle.write('-------------------\n')
        for rpm in result:
            m_rpm = os.path.join(*(rpm.split(os.path.sep)[6:]))
            f_handle.write(m_rpm + '\n')
        f_handle.close()

    # When we've tar'd up the content we can delete the export dir.
    os.chdir(helpers.EXPORTDIR)
    shutil.rmtree(export_path)

    # Split the resulting tar into DVD size chunks & remove the original.
    msg = "Splitting TAR file..."
    helpers.log_msg(msg, 'INFO')
    print msg
    os.system("split -d -b 4200M " + full_tarfile + " " + full_tarfile + "_")
    os.remove(full_tarfile)

    # Temporary until pythonic method is done
    msg = "Calculating Checksums..."
    helpers.log_msg(msg, 'INFO')
    print msg
    os.system('sha256sum ' + short_tarfile + '_* > ' + short_tarfile + '.sha256')

#    helpers.sha256sum()

    # Write the expand script for the disconnected system
    f_handle = open('sat6_export_expand.sh', 'w')
    f_handle.write('#!/bin/bash\n')
    f_handle.write('if [ -f ' + short_tarfile + '_00 ]; then\n')
    f_handle.write('  sha256sum -c ' + short_tarfile + '.sha256\n')
    f_handle.write('  if [ $? -eq 0 ]; then\n')
    f_handle.write('    cat ' + short_tarfile + '_* | tar xzpf -\n')
    f_handle.write('  else\n')
    f_handle.write('    echo ' + short_tarfile + ' checksum failure\n')
    f_handle.write('  fi\n')
    f_handle.write('fi\n')
    f_handle.close()


def write_timestamp(start_time):
    """
    Append the start timestamp to our export record
    """
    f_handle = open('../var/exports.dat', 'a+')
    f_handle.write(start_time + "\n")
    f_handle.close()


def read_timestamp():
    """
    Read the last successful export timestamp from our export record file
    """
    if not os.path.exists('../var/exports.dat'):
        if not os.path.exists('../var'):
            os.makedirs('../var')
        last = None
        return last

    with open('../var/exports.dat', 'r') as f_handle:
        last = None
        for line in (line for line in f_handle if line.rstrip('\n')):
            last = line.rstrip('\n')
    return last


def main():
    """
    Main Routine
    """
    #pylint: disable-msg=R0914,R0915

    # Log the fact we are starting
    msg = "------------- Content export started by ..user.. ----------------"
    helpers.log_msg(msg, 'INFO')

    # Check for sane input
    parser = argparse.ArgumentParser(description='Performs Export of Default Content View.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization', required=True)
    group.add_argument('-a', '--all', help='Export ALL content', required=False,
        action="store_true")
    group.add_argument('-i', '--incr', help='Incremental Export of content since last run',
        required=False, action="store_true")
    group.add_argument('-s', '--since', help='Export content since YYYY-MM-DD HH:MM:SS',
        required=False, type=helpers.valid_date)
    parser.add_argument('-l', '--last', help='Display time of last export', required=False,
        action="store_true")
    args = parser.parse_args()

    # Set our script variables from the input args
    org_name = args.org
    since = args.since

    # Record where we are running from
    script_dir = str(os.getcwd())

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Get the current time - this will be the 'last export' time if the export is OK
    start_time = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')
    print "START: " + start_time

    # Get the last export date. If we're exporting all, this isn't relevant
    # If we are given a start date, use that, otherwise we need to get the last date from file
    # If there is no last export, we'll set an arbitrary start date to grab everything (2000-01-01)
    last_export = read_timestamp()
    export_type = 'incr'
    if args.all:
        print "Performing full content export"
        last_export = '2000-01-01 00:00:00'
        export_type = 'full'
    else:
        if not since:
            if args.last:
                if last_export:
                    print "Last successful export was started at " + last_export
                else:
                    print "Export has never been performed"
                sys.exit(-1)
            if not last_export:
                print "No previous export recorded, performing full content export"
                last_export = '2000-01-01 00:00:00'
                export_type = 'full'
        else:
            last_export = str(since)

            # We have our timestamp so we can kick of an incremental export
            print "Incremental export of content synchronised after " + last_export

    # Check the available space in /var/lib/pulp
    check_disk_space(export_type)

    # TODO: Remove any previous exported content
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
        print helpers.GREEN + msg + helpers.ENDC
    else:
        msg = "Content View Export FAILED"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    # Now we need to process the on-disk export data
    # Find the name of our export dir. This ASSUMES that the export dir is the ONLY dir.
    sat_export_dir = os.walk(helpers.EXPORTDIR).next()[1]
    export_dir = sat_export_dir[0]

    # Run GPG Checks on the exported RPMs
    do_gpg_check(export_dir)

    # Add our exported data to a tarfile
    create_tar(export_dir)

    # We're done. Write the start timestamp to file for next time
    os.chdir(script_dir)
    write_timestamp(start_time)

    # And we're done!
    print helpers.GREEN + "Export complete.\n" + helpers.ENDC
    print 'Please transfer the contents of ' + helpers.EXPORTDIR + \
        'to your disconnected Satellite system content import location. Once the \n' \
        'content is transferred, please run ' + helpers.BOLD + 'sat6_export_expand.sh' \
        + helpers.ENDC + ' to extract it.'


if __name__ == "__main__":
    main()

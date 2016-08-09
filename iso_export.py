#!/usr/bin/python
#title           :iso_export.py
#description     :Exports Satellite 6 ISO content for disconnected environments
#URL             :https://github.com/RedHatSatellite/sat6_disconnected_tools
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Exports ISO content.
"""

import sys, argparse, datetime, os, shutil
import fnmatch, subprocess, tarfile
import simplejson as json
from glob import glob
import helpers


# Promote a content view version
def export_iso(last_export, export_type):
    """
    Export ISO content modules
    Takes the type (full/incr) and the date of the last run
    """

    ISOEXPORTDIR = helpers.EXPORTDIR + '/iso'
    if not os.path.exists(ISOEXPORTDIR):
        print "Creating ISO export directory"
        os.makedirs(ISOEXPORTDIR)

    if export_type == 'full':
        msg = "Exporting all ISO content"
    else:
        msg = "Exporting ISO content from start date " + last_export
    helpers.log_msg(msg, 'INFO')

    if export_type == 'full':
        os.system("find -L /var/lib/pulp/published/http/isos -type f -exec cp --parents -Lrp {} " \
            + ISOEXPORTDIR + " \;")

    else:
        os.system('find -L /var/lib/pulp/published/http/isos -type f -newerct $(date +%Y-%m-%d -d "' \
            + last_export + '") -exec cp --parents -Lrp {} ' + ISOEXPORTDIR + ' \;')


    # At this point the iso/ export dir will contain individual repos - we need to 'normalise' them
    # This is a 'dirty' workaround, but puts the content where it is expected to be for importing.
    #
    # /.../Red_Hat_Enterprise_Linux_Server-Red_Hat_Enterprise_Linux_7_Server_ISOs_x86_64_7_2
    # => /.../content/dist/rhel/server/7/7.2/x86_64/iso

    for dirpath, subdirs, files in os.walk(ISOEXPORTDIR):
        for tdir in subdirs:
            if 'Red_Hat_Enterprise_Linux_7_Server_ISOs_x86_64_7_2' in tdir:
                INDIR = os.path.join(dirpath, tdir)
                OUTDIR = helpers.EXPORTDIR + '/content/dist/rhel/server/7/7.2/x86_64/iso'
            elif 'Red_Hat_Enterprise_Linux_6_Server_ISOs_x86_64_6_8' in tdir:
                INDIR = os.path.join(dirpath, tdir)
                OUTDIR = helpers.EXPORTDIR + '/content/dist/rhel/server/6/6.8/x86_64/iso'


            print INDIR + ' => ' + OUTDIR
            if not os.path.exists(OUTDIR):
                shutil.move(INDIR, OUTDIR)

    return


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

    check_incomplete_sync()


def check_incomplete_sync():
    """
    Check for any sync tasks that are in an Incomplete state.
    These are not paused or locked, but are the orange 100% complete ones in the UI
    """
    repo_list = helpers.get_json(
        helpers.KATELLO_API + "/content_view_versions")

    # Extract the list of repo ids, then check the state of each one.
    incomplete_sync = False
    for repo in repo_list['results']:
        for repo_id in repo['repositories']:
            repo_status = helpers.get_json(
                helpers.KATELLO_API + "/repositories/" + str(repo_id['id']))

            if repo_status['content_type'] == 'file':
                if repo_status['last_sync']['state'] == 'stopped':
                    if repo_status['last_sync']['result'] == 'warning':
                        incomplete_sync = True
                        msg = "Repo ID " + str(repo_id['id']) + " Sync Incomplete"
                        helpers.log_msg(msg, 'DEBUG')

    # If we have detected incomplete sync tasks, ask the user if they want to export anyway.
    # This isn't fatal, but *MAY* lead to inconsistent repositories on the dieconnected sat.
    if incomplete_sync:
        msg = "Incomplete sync jobs detected"
        helpers.log_msg(msg, 'WARNING')
        answer = helpers.query_yes_no("Continue with export?", "no")
        if not answer:
            msg = "Export Aborted"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(-1)
        else:
            msg = "Export continued by user"
            helpers.log_msg(msg, 'INFO')


def locate(pattern, root=os.curdir):
    """Provides simple 'locate' functionality for file search"""
    # pylint: disable=unused-variable
    for path, dirs, files in os.walk(os.path.abspath(root)):
        for filename in fnmatch.filter(files, pattern):
            yield os.path.join(path, filename)


def create_tar(export_dir, export_path):
    """
    Create a TAR of the content we have exported
    Creates a single tar, then splits into DVD size chunks and calculates
    sha256sum for each chunk.
    """
    today = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d')
    msg = "Creating TAR files..."
    helpers.log_msg(msg, 'INFO')
    print msg

    os.chdir(export_dir)
    full_tarfile = helpers.EXPORTDIR + '/iso_export_' + today
    short_tarfile = 'iso_export_' + today
    with tarfile.open(full_tarfile, 'w') as archive:
        archive.add(os.curdir, recursive=True)

    # Get a list of all the RPM content we are exporting
    result = [y for x in os.walk(export_dir) for y in glob(os.path.join(x[0], '*'))]
    if result:
        f_handle = open(helpers.LOGDIR + '/iso_export_' + today + '.log', 'a+')
        f_handle.write('-------------------\n')
        for module in result:
            m_module = os.path.join(*(module.split(os.path.sep)[4:]))
            f_handle.write(m_module + '\n')
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


def write_timestamp(start_time):
    """
    Append the start timestamp to our export record
    """
    f_handle = open('var/iso_exports.dat', 'a+')
    f_handle.write(start_time + "\n")
    f_handle.close()


def read_timestamp():
    """
    Read the last successful export timestamp from our export record file
    """
    if not os.path.exists('var/iso_exports.dat'):
        if not os.path.exists('var'):
            os.makedirs('var')
        last = None
        return last

    with open('var/iso_exports.dat', 'r') as f_handle:
        last = None
        for line in (line for line in f_handle if line.rstrip('\n')):
            last = line.rstrip('\n')
    return last


def main():
    """
    Main Routine
    """
    #pylint: disable-msg=R0912,R0914,R0915

    if helpers.DISCONNECTED:
        msg = "Export cannot be run on the disconnected Satellite host"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    # Who is running this script?
    runuser = helpers.who_is_running()

    # Log the fact we are starting
    msg = "------------- ISO export started by " + runuser + " ----------------"
    helpers.log_msg(msg, 'INFO')

    # Check for sane input
    parser = argparse.ArgumentParser(description='Performs Export of ISO content.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization', required=True)
    group.add_argument('-a', '--all', help='Export ALL ISO content', required=False,
        action="store_true")
    group.add_argument('-i', '--incr', help='Incremental Export of ISO content since last run',
        required=False, action="store_true")
    group.add_argument('-s', '--since', help='Export ISO content since YYYY-MM-DD HH:MM:SS',
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
        print "Performing full ISO content export"
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
                print "No previous export recorded, performing full ISO content export"
                export_type = 'full'
        else:
            last_export = str(since)

            # We have our timestamp so we can kick of an incremental export
            print "Incremental export of ISO content synchronised after " + last_export

    # TODO: Remove any previous exported content
#    os.chdir(helpers.EXPORTDIR)
#    shutil.rmtree()

    # Check if there are any currently running tasks that will conflict with an export
    check_running_tasks()

    # Now we have a CV ID and a starting date, and no conflicting tasks, we can export
    export_iso(last_export, export_type)

    # Now we need to process the on-disk export data
    # Find the name of our export dir. This ASSUMES that the export dir is the ONLY dir.
    sat_export_dir = os.walk(helpers.EXPORTDIR).next()[1]
    export_path = sat_export_dir[0]

    # This portion finds the full directory tree of the ISO content, starting at the level
    # containing the isos root (/var/lib/pulp/published/http/isos/...)
    # pylint: disable=unused-variable
    for dirpath, subdirs, files in os.walk(helpers.EXPORTDIR):
        for tdir in subdirs:
            if 'isos' in tdir:
                export_dir = os.path.join(dirpath, tdir)

    # Add our exported data to a tarfile
    create_tar(export_dir, export_path)

    # We're done. Write the start timestamp to file for next time
    os.chdir(script_dir)
    write_timestamp(start_time)

    # And we're done!
    print helpers.GREEN + "ISO content export complete.\n" + helpers.ENDC
    print 'Please transfer the contents of ' + helpers.EXPORTDIR + \
        ' to your disconnected server content location.\n'


if __name__ == "__main__":
    main()


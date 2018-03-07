#!/usr/bin/python
#title           :sat_export.py
#description     :Exports Satellite 6 Content for disconnected environments
#URL             :https://github.com/RedHatSatellite/sat6_disconnected_tools
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Exports Satellite 6 yum content.
"""

import sys, argparse, datetime, os, shutil, pickle, re
import fnmatch, subprocess, tarfile
import simplejson as json
from glob import glob
from distutils.dir_util import copy_tree
import helpers

try:
    import yaml
except ImportError:
    print "Please install the PyYAML module."
    sys.exit(1)

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
def export_cv(dov_ver, last_export, export_type):
    """
    Export Content View
    Takes the content view version and a start time (API 'since' value)
    """
    if export_type == 'full':
        msg = "Exporting complete DOV version " + str(dov_ver)
    else:
        msg = "Exporting DOV version " + str(dov_ver) + " from start date " + last_export
    helpers.log_msg(msg, 'INFO')

    try:
        if export_type == 'full':
            task_id = helpers.post_json(
                helpers.KATELLO_API + "content_view_versions/" + str(dov_ver) + "/export", \
                    json.dumps(
                        {
                        }
                    ))["id"]
        else:
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
        if helpers.MAILOUT:
            helpers.tf.seek(0)
            output = "{}".format(helpers.tf.read())
            subject = "Satellite 6 export failure"
            helpers.mailout(subject, output)
        sys.exit(1)

    # Trap some other error conditions
    if "Required lock is already taken" in str(task_id):
        msg = "Unable to start export - Sync in progress"
        helpers.log_msg(msg, 'ERROR')
        if helpers.MAILOUT:
            helpers.tf.seek(0)
            output = "{}".format(helpers.tf.read())
            subject = "Satellite 6 export failure"
            helpers.mailout(subject, output)
        sys.exit(1)

    msg = "Export started, task_id = " + str(task_id)
    helpers.log_msg(msg, 'DEBUG')

    return str(task_id)


def export_repo(repo_id, last_export, export_type):
    """
    Export individual repository
    Takes the repository id and a start time (API 'since' value)
    """
    if export_type == 'full':
        msg = "Exporting repository id " + str(repo_id)
    else:
        msg = "Exporting repository id " + str(repo_id) + " from start date " + last_export
    helpers.log_msg(msg, 'DEBUG')

    try:
        if export_type == 'full':
            task_id = helpers.post_json(
                helpers.KATELLO_API + "repositories/" + str(repo_id) + "/export", \
                    json.dumps(
                        {
                        }
                    ))["id"]
        else:
            task_id = helpers.post_json(
                helpers.KATELLO_API + "repositories/" + str(repo_id) + "/export/", \
                    json.dumps(
                        {
                            "since": last_export,
                        }
                    ))["id"]
    except: # pylint: disable-msg=W0702
        msg = "Unable to start export - Conflicting Sync or Export already in progress"
        helpers.log_msg(msg, 'ERROR')
        if helpers.MAILOUT:
            helpers.tf.seek(0)
            output = "{}".format(helpers.tf.read())
            subject = "Satellite 6 export failure"
            helpers.mailout(subject, output)
        sys.exit(1)

    # Trap some other error conditions
    if "Required lock is already taken" in str(task_id):
        msg = "Unable to start export - Sync in progress"
        helpers.log_msg(msg, 'ERROR')
        if helpers.MAILOUT:
            helpers.tf.seek(0)
            output = "{}".format(helpers.tf.read())
            subject = "Satellite 6 export failure"
            helpers.mailout(subject, output)
        sys.exit(1)

    msg = "Export started, task_id = " + str(task_id)
    helpers.log_msg(msg, 'DEBUG')

    return str(task_id)


def export_iso(repo_id, repo_label, repo_relative, last_export, export_type):
    """
    Export iso repository
    Takes the repository id and a start time (find newer than value)
    """
    numfiles = 0
    ISOEXPORTDIR = helpers.EXPORTDIR + '/iso'
    if not os.path.exists(ISOEXPORTDIR):
        os.makedirs(ISOEXPORTDIR)

    if export_type == 'full':
        msg = "Exporting ISO repository id " + str(repo_id)
    else:
        msg = "Exporting ISO repository id " + str(repo_id) + " from start date " + last_export
    helpers.log_msg(msg, 'INFO')


    # This will currently export ALL ISO, not just the selected repo
    if export_type == 'full':
        msg = "Exporting all ISO content"
    else:
        msg = "Exporting ISO content from start date " + last_export
    helpers.log_msg(msg, 'INFO')

    msg = "  Copying updated files for export..."
    colx = "{:<70}".format(msg)
    print colx[:70],
    helpers.log_msg(msg, 'INFO')
    # Force the status message to be shown to the user
    sys.stdout.flush()

    if export_type == 'full':
        os.system('find -L /var/lib/pulp/published/http/isos/*' + repo_label \
            + ' -type f -exec cp --parents -Lrp {} ' + ISOEXPORTDIR + " \;")
    else:
        os.system('find -L /var/lib/pulp/published/http/isos/*' + repo_label \
            + ' -type f -newerct $(date +%Y-%m-%d -d "' + last_export + '") -exec cp --parents -Lrp {} ' \
            + ISOEXPORTDIR + ' \;')
        # We need to copy the manifest anyway, otherwise we'll cause import issues if we have an empty repo
        os.system('find -L /var/lib/pulp/published/http/isos/*' + repo_label \
            + ' -name PULP_MANIFEST -exec cp --parents -Lrp {} ' + ISOEXPORTDIR + ' \;')


    # At this point the iso/ export dir will contain individual repos - we need to 'normalise' them
    for dirpath, subdirs, files in os.walk(ISOEXPORTDIR):
        for tdir in subdirs:
            if repo_label in tdir:
                # This is where the exported ISOs for our repo are located
                INDIR = os.path.join(dirpath, tdir)
                # And this is where we want them to be moved to so we can export them in Satellite format
                # We need to knock off '<org_name>/Library/' from beginning of repo_relative and replace with export/
                exportpath = "/".join(repo_relative.strip("/").split('/')[2:])
                OUTDIR = helpers.EXPORTDIR + '/export/' + exportpath

                # Move the files into the final export tree
                if not os.path.exists(OUTDIR):
                    shutil.move(INDIR, OUTDIR)

                    os.chdir(OUTDIR)
                    numfiles = len([f for f in os.walk(".").next()[2] if f[ -8: ] != "MANIFEST"])

                    msg = "File Export OK (" + str(numfiles) + " new files)"
                    helpers.log_msg(msg, 'INFO')
                    print helpers.GREEN + msg + helpers.ENDC

    return numfiles


def export_puppet(repo_id, repo_label, repo_relative, last_export, export_type, pforge):
    """
    Export Puppet modules
    Takes the type (full/incr) and the date of the last run
    """
    numfiles = 0
    PUPEXPORTDIR = helpers.EXPORTDIR + '/puppet'
    if not os.path.exists(PUPEXPORTDIR):
        os.makedirs(PUPEXPORTDIR)

    if export_type == 'full':
        msg = "Exporting Puppet repository id " + str(repo_id)
    else:
        msg = "Exporting Puppet repository id " + str(repo_id) + " from start date " + last_export
    helpers.log_msg(msg, 'INFO')

    # This will currently export ALL ISO, not just the selected repo
    if export_type == 'full':
        msg = "Exporting all Puppet content"
    else:
        msg = "Exporting Puppet content from start date " + last_export
    helpers.log_msg(msg, 'INFO')

    msg = "  Copying updated files for export..."
    colx = "{:<70}".format(msg)
    print colx[:70],
    helpers.log_msg(msg, 'INFO')
    # Force the status message to be shown to the user
    sys.stdout.flush()

    if export_type == 'full':
        os.system('find -L /var/lib/pulp/published/puppet/http/repos/*' + repo_label \
            + ' -type f -exec cp --parents -Lrp {} ' + PUPEXPORTDIR + ' \;')
    else:
        os.system('find -L /var/lib/pulp/published/puppet/http/repos/*' + repo_label \
            + ' -type f -newerct $(date +%Y-%m-%d -d "' + last_export + '") -exec cp --parents -Lrp {} '\
            + PUPEXPORTDIR + ' \;')
        # We need to copy the manifest anyway, otherwise we'll cause import issues if we have an empty repo
        os.system('find -L /var/lib/pulp/published/puppet/http/repos/*' + repo_label \
            + ' -name modules.json -exec cp --parents -Lrp {} ' + PUPEXPORTDIR + ' \;')

    # At this point the puppet/ export dir will contain individual repos - we need to 'normalise' them
    for dirpath, subdirs, files in os.walk(PUPEXPORTDIR):
        for tdir in subdirs:
            if repo_label in tdir:
                # This is where the exported ISOs for our repo are located
                INDIR = os.path.join(dirpath, tdir)
                # And this is where we want them to be moved to so we can export them in Satellite format
                # We need to knock off '<org_name>/Library/' from beginning of repo_relative and replace with export/
                exportpath = "/".join(repo_relative.strip("/").split('/')[2:])
                OUTDIR = helpers.EXPORTDIR + '/export/' + exportpath

                # Move the files into the final export tree
                if not os.path.exists(OUTDIR):
                    shutil.move(INDIR, OUTDIR)

                    os.chdir(OUTDIR)
                    numfiles = sum([len(files) for r, d, files in os.walk(OUTDIR)])
                    # Subtract the manifest from the number of files:
                    numfiles = numfiles - 1

                    msg = "Puppet Export OK (" + str(numfiles) + " new files)"
                    helpers.log_msg(msg, 'INFO')
                    print helpers.GREEN + msg + helpers.ENDC

    # If we are dealing with Puppet_Forge, create a second bundle for import to puppet-forge-server
    if pforge:
        # Only relevant if this is the Puppet_Forge repo...
        if 'Puppet_Forge' in OUTDIR:
            PFEXPORTDIR = helpers.EXPORTDIR + '/export/puppetforge'
            if not os.path.exists(PFEXPORTDIR):
                os.makedirs(PFEXPORTDIR)
            os.system('find ' + OUTDIR + ' -name "*.gz" -exec cp {} ' + PFEXPORTDIR + ' \;')

    return numfiles


def export_manifest():
    """
    Copies manifest downloaded by 'download_manifest.py' into the export bundle
    """
    if os.path.exists(helpers.EXPORTDIR + '/manifest'):
        msg = 'Found manifest to export'
        helpers.log_msg(msg, 'DEBUG')
        MFSTEXPORTDIR = helpers.EXPORTDIR + '/export/manifest'
        if not os.path.exists(MFSTEXPORTDIR):
            os.makedirs(MFSTEXPORTDIR)
        os.system('cp ' + helpers.EXPORTDIR + '/manifest/* ' + MFSTEXPORTDIR)


def count_packages(repo_id):
    """
    Return the number of packages/erratum in a respository
    """
    result = helpers.get_json(
        helpers.KATELLO_API + "repositories/" + str(repo_id)
            )

    numpkg = result['content_counts']['rpm']
    numerrata = result['content_counts']['erratum']

    return str(numpkg) + ':' + str(numerrata)


def check_running_tasks(label, name):
    """
    Check for any currently running Sync or Export tasks
    Exits script if any Synchronize or Export tasks are found in a running state.
    """
    #pylint: disable-msg=R0912,R0914,R0915
    tasks = helpers.get_p_json(
        helpers.FOREMAN_API + "tasks/", \
                json.dumps(
                    {
                        "per_page": "100",
                    }
                ))

    # From the list of tasks, look for any running export or sync jobs.
    # If e have any we exit, as we can't export in this state.
    ok_to_export = True
    for task_result in tasks['results']:
        if task_result['state'] == 'running':
            if task_result['humanized']['action'] == 'Export':
                if task_result['input']['repository']['label'] == label:
                    msg = "Unable to export due to export task in progress"
                    if name == 'DoV':
                        helpers.log_msg(msg, 'ERROR')
                        sys.exit(1)
                    else:
                        helpers.log_msg(msg, 'WARNING')
                        ok_to_export = False
            if task_result['humanized']['action'] == 'Synchronize':
                if task_result['input']['repository']['label'] == label:
                    msg = "Unable to export due to sync task in progress"
                    if name == 'DoV':
                        helpers.log_msg(msg, 'ERROR')
                        sys.exit(1)
                    else:
                        helpers.log_msg(msg, 'WARNING')
                        ok_to_export = False
        if task_result['state'] == 'paused':
            if task_result['humanized']['action'] == 'Export':
                if task_result['input']['repository']['label'] == label:
                    msg = "Unable to export due to paused export task - Please resolve this issue."
                    if name == 'DoV':
                        helpers.log_msg(msg, 'ERROR')
                        sys.exit(1)
                    else:
                        helpers.log_msg(msg, 'WARNING')
                        ok_to_export = False
            if task_result['humanized']['action'] == 'Synchronize':
                if task_result['input']['repository']['label'] == label:
                    msg = "Unable to export due to paused sync task."
                    if name == 'DoV':
                        helpers.log_msg(msg, 'ERROR')
                        sys.exit(1)
                    else:
                        helpers.log_msg(msg, 'WARNING')
                        ok_to_export = False

    check_incomplete_sync()
    return ok_to_export


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

            if repo_status['content_type'] == 'yum':
                if repo_status['last_sync'] is None:
                    if repo_status['url'] is None:
                        msg = "Repo ID " + str(repo_id['id']) + " No Sync Configured"
                        #helpers.log_msg(msg, 'DEBUG')
                elif repo_status['last_sync']['state'] == 'stopped':
                    if repo_status['last_sync']['result'] == 'warning':
                        incomplete_sync = True
                        msg = "Repo ID " + str(repo_id['id']) + " Sync Incomplete"
                        helpers.log_msg(msg, 'DEBUG')

    # If we have detected incomplete sync tasks, ask the user if they want to export anyway.
    # This isn't fatal, but *MAY* lead to inconsistent repositories on the dieconnected sat.
    if incomplete_sync:
        msg = "Incomplete sync jobs detected"
        helpers.log_msg(msg, 'WARNING')
        if not args.unattended:
            answer = helpers.query_yes_no("Continue with export?", "no")
            if not answer:
                msg = "Export Aborted"
                helpers.log_msg(msg, 'ERROR')
                sys.exit(3)
            else:
                msg = "Export continued by user"
                helpers.log_msg(msg, 'INFO')
        else:
            msg = "Export Aborted"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(3)


def check_disk_space(export_type,unattended):
    """
    Check the disk usage of the pulp partition
    For a full export we need at least 50% free, as we spool to /var/lib/pulp.
    """
    pulp_used = str(helpers.disk_usage('/var/lib/pulp'))
    if export_type == 'full' and int(float(pulp_used)) > 50:
        msg = "Insufficient space in /var/lib/pulp for a full export. >50% free space is required."
        helpers.log_msg(msg, 'WARNING')
        if not unattended:
            answer = helpers.query_yes_no("Continue with export?", "no")
            if not answer:
                msg = "Export Aborted"
                helpers.log_msg(msg, 'ERROR')
                sys.exit(3)
            else:
                msg = "Export continued by user"
                helpers.log_msg(msg, 'INFO')
        else:
            msg = "Export Aborted"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(3)


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
    msg = "Checking GPG integrity of exported RPMs..."
    helpers.log_msg(msg, 'INFO')
    output = "{:<70}".format(msg)
    print output[:70],
    # Force the status message to be shown to the user
    sys.stdout.flush()

    badrpms = []
    os.chdir(export_dir)
    for rpm in locate("*.rpm"):
        return_code = subprocess.call("rpm -K " + rpm, shell=True, stdout=open(os.devnull, 'wb'))

        # A non-zero return code indicates a GPG check failure.
        if return_code != 0:
            # For display purposes, strip the first 6 directory elements
            rpmnew = os.path.join(*(rpm.split(os.path.sep)[6:]))
            badrpms.append(rpmnew)

    # If we have any bad ones we need to fail the export.
    if len(badrpms) != 0:
        print helpers.RED + "GPG Check FAILED" + helpers.ENDC
        msg = "The following RPM's failed the GPG check.."
        helpers.log_msg(msg, 'ERROR')
        for badone in badrpms:
            msg = badone
            helpers.log_msg(msg, 'ERROR')
        msg = "------ Export Aborted ------"
        helpers.log_msg(msg, 'INFO')
        if helpers.MAILOUT:
            helpers.tf.seek(0)
            output = "{}".format(helpers.tf.read())
            subject = "Satellite 6 export failure - GPG checksum failure"
            message = "GPG check of exported RPMs failed. Check logs for details\n\n" + output
            helpers.mailout(subject, message)
        sys.exit(1)
    else:
        msg = "GPG check completed successfully"
        helpers.log_msg(msg, 'INFO')
        print helpers.GREEN + "GPG Check - Pass" + helpers.ENDC


def create_tar(export_dir, name, export_history):
    """
    Create a TAR of the content we have exported
    Creates a single tar, then splits into DVD size chunks and calculates
    sha256sum for each chunk.
    """
    today = datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d-%H%M')
    msg = "Creating TAR files..."
    helpers.log_msg(msg, 'INFO')
    print msg

    # Add this export to the export_history list
    fname = today + '_' + name
    export_history.append(fname)
    pickle.dump(export_history, open(vardir + '/exporthistory_' + name + '.pkl', 'wb'))
    pickle.dump(export_history, open(export_dir + '/exporthistory_' + name + '.pkl', 'wb'))

    os.chdir(export_dir)
    full_tarfile = helpers.EXPORTDIR + '/sat6_export_' + today + '_' + name
    short_tarfile = 'sat6_export_' + today + '_' + name
    with tarfile.open(full_tarfile, 'w') as archive:
        archive.add(os.curdir, recursive=True)

    # Get a list of all the RPM content we are exporting
    result = [y for x in os.walk(export_dir) for y in glob(os.path.join(x[0], '*.rpm'))]
    if result:
        f_handle = open(helpers.LOGDIR + '/export_' + today + '_' + name + '.log', 'a+')
        f_handle.write('-------------------\n')
        for rpm in result:
            m_rpm = os.path.join(*(rpm.split(os.path.sep)[6:]))
            f_handle.write(m_rpm + '\n')
        f_handle.close()

    # When we've tar'd up the content we can delete the export dir.
    os.chdir(helpers.EXPORTDIR)
    shutil.rmtree(export_dir)
    if os.path.exists(helpers.EXPORTDIR + "/iso"):
        shutil.rmtree(helpers.EXPORTDIR + "/iso")
    if os.path.exists(helpers.EXPORTDIR + "/puppet"):
        shutil.rmtree(helpers.EXPORTDIR + "/puppet")

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


def prep_export_tree(org_name, basepaths):
    """
    Function to combine individual export directories into single export tree
    Export top level contains /content and /custom directories with 'listing'
    files through the tree.
    """
    msg = "Preparing export directory tree..."
    helpers.log_msg(msg, 'INFO')
    print msg
    devnull = open(os.devnull, 'wb')
    if not os.path.exists(helpers.EXPORTDIR + "/export"):
        os.makedirs(helpers.EXPORTDIR + "/export")

    # Copy the content from each exported repo into a common /export structure
    for basepath in basepaths:
        msg = "Processing " + basepath
        helpers.log_msg(msg, 'DEBUG')
        subprocess.call("cp -rp " + basepath + "/" + org_name + \
            "/Library/* " + helpers.EXPORTDIR + "/export", shell=True, stdout=devnull, stderr=devnull)

        # Remove original directores
        os.system("rm -rf " + basepath + "/")

    # We need to re-generate the 'listing' files as we will have overwritten some during the merge
    msg = "Rebuilding listing files..."
    helpers.log_msg(msg, 'INFO')
    print msg
    create_listing_file(helpers.EXPORTDIR + "/export")

    # pylint: disable=unused-variable
    for root, directories, filenames in os.walk(helpers.EXPORTDIR + "/export"):
        for subdir in directories:
            currentdir = os.path.join(root, subdir)
            create_listing_file(currentdir)


def get_immediate_subdirectories(a_dir):
    """ Return a list of subdirectories """
    return [name for name in os.listdir(a_dir) if os.path.isdir(os.path.join(a_dir, name))]


def create_listing_file(directory):
    """
    Function to create the listing file containing the subdirectories
    """
    listing_file = open(directory + "/listing", "w")
    sorted_subdirs = sorted(get_immediate_subdirectories(directory))
    for directory in sorted_subdirs:
        listing_file.write(directory + "\n")
    listing_file.close()


def read_pickle(name):
    """
    Function to read the last export dates from an existing pickle
    """
    if not os.path.exists(vardir + '/exports_' + name + '.pkl'):
        if not os.path.exists(vardir):
            os.makedirs(vardir)
        export_times = {}
        return export_times

    # Read in the export time pickle
    export_times = pickle.load(open(vardir + '/exports_' + name + '.pkl', 'rb'))
    return export_times


def get_product(org_id, cp_id):
    """
    Find and return the label of the given product ID
    """
    prod_list = helpers.get_p_json(
        helpers.KATELLO_API + "/products/", \
                json.dumps(
                        {
                           "organization_id": org_id,
                           "per_page": '1000',
                        }
                ))

    for prod in prod_list['results']:
        if prod['cp_id'] == cp_id:
            prodlabel = prod['label']
            return prodlabel


def main(args):
    """
    Main Routine
    """
    #pylint: disable-msg=R0912,R0914,R0915

    # Who is running this script?
    runuser = helpers.who_is_running()

    # Set the base dir of the script and where the var data is
    global dir
    global vardir
    dir = os.path.dirname(__file__)
    vardir = os.path.join(dir, 'var')
    confdir = os.path.join(dir, 'config')

    # Check for sane input
    parser = argparse.ArgumentParser(description='Performs Export of Default Content View.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization (Uses default if not specified)',
        required=False)
    parser.add_argument('-e', '--env', help='Environment config', required=False)
    group.add_argument('-a', '--all', help='Export ALL content', required=False,
        action="store_true")
    group.add_argument('-i', '--incr', help='Incremental Export of content since last run',
        required=False, action="store_true")
    group.add_argument('-s', '--since', help='Export content since YYYY-MM-DD HH:MM:SS',
        required=False, type=helpers.valid_date)
    parser.add_argument('-l', '--last', help='Display time of last export', required=False,
        action="store_true")
    parser.add_argument('-L', '--list', help='Display export history', required=False,
        action="store_true")
    parser.add_argument('--nogpg', help='Skip GPG checking', required=False,
        action="store_true")
    parser.add_argument('-u', '--unattended', help='Answer any prompts safely, allowing automated usage',
        required=False, action="store_true")
    parser.add_argument('--notar', help='Skip TAR creation', required=False,
        action="store_true")
    parser.add_argument('--forcexport', help='Force export on import-only satellite', required=False,
        action="store_true")
    parser.add_argument('-r', '--repodata', help='Include repodata for repos with no new packages',
        required=False, action="store_true")
    parser.add_argument('-p', '--puppetforge', help='Include puppet-forge-server format Puppet Forge repo',
        required=False, action="store_true")
    args = parser.parse_args()

    # If we are set as the 'DISCONNECTED' satellite, we will generally be IMPORTING content.
    if helpers.DISCONNECTED:
        if not args.forcexport:
            msg = "Export cannot be run on the disconnected Satellite host"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(1)

    # Set our script variables from the input args
    if args.org:
        org_name = args.org
    else:
       org_name = helpers.ORG_NAME
    since = args.since

    if args.puppetforge:
        pforge = True
    else:
        pforge = False

    # Record where we are running from
    script_dir = str(os.getcwd())

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)
    exported_repos = []
    export_history = []
    basepaths = []
    package_count = {}
    # If a specific environment is requested, find and read that config file
    repocfg = os.path.join(dir, confdir + '/exports.yml')
    if args.env:
        if not os.path.exists(repocfg):
            msg = 'Config file ' + confdir + '/exports.yml not found.'
            helpers.log_msg(msg, 'ERROR')
            sys.exit(1)

        cfg = yaml.safe_load(open(repocfg, 'r'))
        ename = args.env
        erepos = []
        validrepo = False
        for x in cfg['exports']:
            if cfg['exports'][x]['name'] == ename:
                validrepo = True
                erepos = cfg['exports'][x]['repos']

        if not validrepo:
            msg = 'Unable to find export config for ' + ename
            helpers.log_msg(msg, 'ERROR')
            sys.exit(1)

        msg = "Specific environment export called for " + ename + "."
        helpers.log_msg(msg, 'DEBUG')
        for repo in erepos:
            msg = "  - " + repo
            helpers.log_msg(msg, 'DEBUG')

    else:
        ename = 'DoV'
        label = 'DoV'
        msg = "DoV export called"
        helpers.log_msg(msg, 'DEBUG')

    # Read the last export date pickle for our selected repo group.
    export_times = read_pickle(ename)
    export_type = 'incr'

    # Open the export history pickle so we can append to it
    if os.path.exists(vardir + '/exporthistory_' + ename + '.pkl'):
        export_history = pickle.load(open(vardir + '/exporthistory_' + ename + '.pkl', 'rb'))

    if args.all:
        print "Performing full content export for " + ename
        export_type = 'full'
        since = False
    else:
        if not since:
            since = False
            if args.last:
                if export_times:
                    print "Last successful export for " + ename + ":"
                    for time in export_times:
                        repo = "{:<70}".format(time)
                        print repo[:70] + '\t' + str(export_times[time])
                else:
                    print "Export has never been performed for " + ename
                sys.exit(0)
            if not export_times:
                print "No prior export recorded for " + ename + ", performing full content export"
                export_type = 'full'

            # Display the full export history
            if args.list:
                if export_history:
                    print "Export history for " + ename + ":"
                    for item in export_history:
                        print item
                    sys.exit(0)
                else:
                    print "Export has never been performed for " + ename
                sys.exit(0)

        else:
            # Re-populate export_times dictionary so each repo has 'since' date
            since_export = str(since)

            # We have our timestamp so we can kick of an incremental export
            print "Incremental export of content for " + ename + " synchronised after " \
            + str(since)

    # Log the fact we are starting
    msg = "------------- Content export started by " + runuser + " ----------------"
    if args.env:
        msg = "------ " + ename + " Content export started by " + runuser + " ---------"
    helpers.log_msg(msg, 'INFO')


    # Get the current time - this will be the 'last export' time if the export is OK
    start_time = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')
    print "START: " + start_time + " (" + ename + " export)"


    # Check the available space in /var/lib/pulp
    check_disk_space(export_type,args.unattended)

    # Remove any previous exported content left behind by prior unclean exit
    if os.path.exists(helpers.EXPORTDIR + '/export'):
        msg = "Removing existing export directory"
        helpers.log_msg(msg, 'DEBUG')
        shutil.rmtree(helpers.EXPORTDIR + '/export')

    # Collect a list of enabled repositories. This is needed for:
    # 1. Matching specific repo exports, and
    # 2. Running import sync per repo on the disconnected side
    repolist = helpers.get_p_json(
        helpers.KATELLO_API + "/repositories/", \
                json.dumps(
                        {
                           "organization_id": org_id,
                           "per_page": '1000',
                        }
                ))

    # If we are running a full DoV export we run a different set of API calls...
    if ename == 'DoV':
        cola = "Exporting DoV"
        if export_type == 'incr' and 'DoV' in export_times:
            last_export = export_times['DoV']
            if since:
                last_export = since_export
            else:
                # To ensure we get ALL the packages reset the time to midnight on the last_export day
                last_export = last_export.split(' ')[0] + " 00:00:00"
            colb = "(INCR since " + last_export + ")"
        else:
            export_type = 'full'
            last_export = '2000-01-01 12:00:00' # This is a dummy value, never used.
            colb = "(FULL)"
        msg = cola + " " + colb
        helpers.log_msg(msg, 'INFO')
        output = "{:<70}".format(cola)
        print output[:70] + ' ' + colb

        # Check if there are any currently running tasks that will conflict with an export
        check_running_tasks(label, ename)

        # Get the version of the CV (Default Org View) to export
        dov_ver = get_cv(org_id)

        # Now we have a CV ID and a starting date, and no conflicting tasks, we can export
        export_id = export_cv(dov_ver, last_export, export_type)

        # Now we need to wait for the export to complete
        helpers.wait_for_task(export_id, 'export')

        # Check if the export completed OK. If not we exit the script.
        tinfo = helpers.get_task_status(export_id)
        if tinfo['state'] != 'running' and tinfo['result'] == 'success':
            msg = "Content View Export OK"
            helpers.log_msg(msg, 'INFO')
            print helpers.GREEN + msg + helpers.ENDC

            # Update the export timestamp for this repo
            export_times['DoV'] = start_time

            # Generate a list of repositories that were exported
            for repo_result in repolist['results']:
                if repo_result['content_type'] == 'yum':
                    # Add the repo to the successfully exported list
                    exported_repos.append(repo_result['label'])

        else:
            msg = "Content View Export FAILED"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(1)

    else:
        # Verify that defined repos exist in Satellite
        for repo in erepos:
            repo_in_sat = False
            for repo_x in repolist['results']:
                if re.findall("\\b" + repo + "\\b$", repo_x['label']):
                    repo_in_sat = True
                    break
            if repo_in_sat == False:
                msg = "'" + repo + "' not found in Satellite"
                helpers.log_msg(msg, 'WARNING')

        # Process each repo
        for repo_result in repolist['results']:
            if repo_result['content_type'] == 'yum':
                # If we have a match, do the export
                if repo_result['label'] in erepos:
                    # Extract the last export time for this repo
                    orig_export_type = export_type
                    cola = "Export " + repo_result['label']
                    if export_type == 'incr' and repo_result['label'] in export_times:
                        last_export = export_times[repo_result['label']]
                        if since:
                            last_export = since_export
                        else:
                            # To ensure we get ALL the packages reset the time to midnight on the last_export day
                            last_export = last_export.split(' ')[0] + " 00:00:00"
                        colb = "(INCR since " + last_export + ")"
                    else:
                        export_type = 'full'
                        last_export = '2000-01-01 12:00:00' # This is a dummy value, never used.
                        colb = "(FULL)"
                    msg = cola + " " + colb
                    helpers.log_msg(msg, 'INFO')
                    output = "{:<70}".format(cola)
                    print output[:70] + ' ' + colb

                    # Check if there are any currently running tasks that will conflict
                    ok_to_export = check_running_tasks(repo_result['label'], ename)

                    if ok_to_export:
                        # Count the number of packages
                        numpkg = count_packages(repo_result['id'])
                        package_count[repo_result['label']] = numpkg

                        # Trigger export on the repo
                        export_id = export_repo(repo_result['id'], last_export, export_type)

                        # Now we need to wait for the export to complete
                        helpers.wait_for_task(export_id, 'export')

                        # Check if the export completed OK. If not we exit the script.
                        tinfo = helpers.get_task_status(export_id)
                        if tinfo['state'] != 'running' and tinfo['result'] == 'success':
                            # Count the number of exported packages
                            # First resolve the product label - this forms part of the export path
                            product = get_product(org_id, repo_result['product']['cp_id'])
                            # Now we can build the export path itself

                            # Satellite 6.3 uses a new backend_identifier key in the API result
                            if 'backend_identifier' in repo_result:
                                basepath = helpers.EXPORTDIR + "/" + repo_result['backend_identifier']
                            else:
                                basepath = helpers.EXPORTDIR + "/" + org_name + "-" + product + "-" + repo_result['label']

                            # Add to the basepath list so we can use specific paths later
                            # (Introduced due to path name changes in Sat6.3)
                            basepaths.append(basepath)

                            if export_type == 'incr':
                                basepath = basepath + "-incremental"
                            exportpath = basepath + "/" + repo_result['relative_path']
                            msg = "\nExport path = " + exportpath
                            helpers.log_msg(msg, 'DEBUG')

                            if not os.path.exists(exportpath):
                                msg = exportpath + " was not created.\nCheck permissions/SELinux on export dir"
                                helpers.log_msg(msg, 'ERROR')
                                if helpers.MAILOUT:
                                    helpers.tf.seek(0)
                                    output = "{}".format(helpers.tf.read())
                                    subject = "Satellite 6 export failure"
                                    helpers.mailout(subject, output)
                                sys.exit(1)

                            # Count the number of .rpm files in the exported repo (recursively)
                            numrpms = 0
                            for dirpath, dirs, files in os.walk(exportpath):
                                for filename in files:
                                    fname = os.path.join(dirpath,filename)
                                    if fname.endswith('.rpm'):
                                        numrpms = numrpms + 1

                            msg = "Repository Export OK (" + str(numrpms) + " new packages)"
                            helpers.log_msg(msg, 'INFO')
                            print helpers.GREEN + msg + helpers.ENDC

                            # Update the export timestamp for this repo
                            export_times[repo_result['label']] = start_time

                            # Add the repo to the successfully exported list
                            if numrpms != 0 or args.repodata:
                                msg = "Adding " + repo_result['label'] + " to export list"
                                helpers.log_msg(msg, 'DEBUG')
                                exported_repos.append(repo_result['label'])
                            else:
                                msg = "Not including repodata for empty repo " + repo_result['label']
                                helpers.log_msg(msg, 'DEBUG')

                        else:
                            msg = "Export FAILED"
                            helpers.log_msg(msg, 'ERROR')

                        # Reset the export type to the user specified, in case we overrode it.
                        export_type = orig_export_type

                else:
                    msg = "Skipping  " + repo_result['label']
                    helpers.log_msg(msg, 'DEBUG')

            # Handle FILE type exports (ISO repos)
            elif repo_result['content_type'] == 'file':
                # If we have a match, do the export
                if repo_result['label'] in erepos:
                    # Extract the last export time for this repo
                    orig_export_type = export_type
                    cola = "Export " + repo_result['label']
                    if export_type == 'incr' and repo_result['label'] in export_times:
                        last_export = export_times[repo_result['label']]
                        if since:
                            last_export = since_export
                        else:
                            # To ensure we get ALL the packages reset the time to midnight on the last_export day
                            last_export = last_export.split(' ')[0] + " 00:00:00"
                        colb = "(INCR since " + last_export + ")"
                    else:
                        export_type = 'full'
                        last_export = '2000-01-01 12:00:00' # This is a dummy value, never used.
                        colb = "(FULL)"
                    msg = cola + " " + colb
                    helpers.log_msg(msg, 'INFO')
                    output = "{:<70}".format(cola)
                    print output[:70] + ' ' + colb

                    # Check if there are any currently running tasks that will conflict
                    ok_to_export = check_running_tasks(repo_result['label'], ename)

                    if ok_to_export:
                        # Trigger export on the repo
                        numfiles = export_iso(repo_result['id'], repo_result['label'], repo_result['relative_path'], last_export, export_type)

                        # Reset the export type to the user specified, in case we overrode it.
                        export_type = orig_export_type

                        # Update the export timestamp for this repo
                        export_times[repo_result['label']] = start_time

                        # Add the repo to the successfully exported list
                        if numfiles != 0 or args.repodata:
                            msg = "Adding " + repo_result['label'] + " to export list"
                            helpers.log_msg(msg, 'DEBUG')
                            exported_repos.append(repo_result['label'])
                        else:
                            msg = "Not including repodata for empty repo " + repo_result['label']
                            helpers.log_msg(msg, 'DEBUG')

                else:
                    msg = "Skipping  " + repo_result['label']
                    helpers.log_msg(msg, 'DEBUG')

            elif repo_result['content_type'] == 'puppet':
                # If we have a match, do the export
                if repo_result['label'] in erepos:
                    # Extract the last export time for this repo
                    orig_export_type = export_type
                    cola = "Export " + repo_result['label']
                    if export_type == 'incr' and repo_result['label'] in export_times:
                        last_export = export_times[repo_result['label']]
                        if since:
                            last_export = since_export
                        else:
                            # To ensure we get ALL the packages reset the time to midnight on the last_export day
                            last_export = last_export.split(' ')[0] + " 00:00:00"
                        colb = "(INCR since " + last_export + ")"
                    else:
                        export_type = 'full'
                        last_export = '2000-01-01 12:00:00' # This is a dummy value, never used.
                        colb = "(FULL)"
                    msg = cola + " " + colb
                    helpers.log_msg(msg, 'INFO')
                    output = "{:<70}".format(cola)
                    print output[:70] + ' ' + colb

                    # Check if there are any currently running tasks that will conflict
                    ok_to_export = check_running_tasks(repo_result['label'], ename)

                    if ok_to_export:
                        # Trigger export on the repo
                        numfiles = export_puppet(repo_result['id'], repo_result['label'], repo_result['relative_path'], last_export, export_type, pforge)

                        # Reset the export type to the user specified, in case we overrode it.
                        export_type = orig_export_type

                        # Update the export timestamp for this repo
                        export_times[repo_result['label']] = start_time

                        # Add the repo to the successfully exported list
                        if numfiles != 0 or args.repodata:
                            msg = "Adding " + repo_result['label'] + " to export list"
                            helpers.log_msg(msg, 'DEBUG')
                            exported_repos.append(repo_result['label'])
                        else:
                            msg = "Not including repodata for empty repo " + repo_result['label']
                            helpers.log_msg(msg, 'DEBUG')

                else:
                    msg = "Skipping  " + repo_result['label']
                    helpers.log_msg(msg, 'DEBUG')


    # Combine resulting directory structures into a single repo format (top level = /content)
    prep_export_tree(org_name, basepaths)

    # Now we need to process the on-disk export data.
    # Define the location of our exported data.
    export_dir = helpers.EXPORTDIR + "/export"

    # Write out the list of exported repos and the package counts. These will be transferred to the
    # disconnected system and used to perform the repo sync tasks during the import.
    pickle.dump(exported_repos, open(export_dir + '/exported_repos.pkl', 'wb'))
    pickle.dump(package_count, open(export_dir + '/package_count.pkl', 'wb'))

    # Run GPG Checks on the exported RPMs
    if not args.nogpg:
        do_gpg_check(export_dir)

    # Copy in the manifest, if it has been downloaded
    export_manifest()

    # Add our exported data to a tarfile
    if not args.notar:
        create_tar(export_dir, ename, export_history)
    else:
        # We need to manually clean up a couple of working files from the export
        if os.path.exists(helpers.EXPORTDIR + "/iso"):
            shutil.rmtree(helpers.EXPORTDIR + "/iso")
        if os.path.exists(helpers.EXPORTDIR + "/puppet"):
            shutil.rmtree(helpers.EXPORTDIR + "/puppet")
        os.system("rm -f " + helpers.EXPORTDIR + "/*.pkl")
        os.system("rm -f " + export_dir + "/*.pkl")

        # Copy export_dir to cdn_export to prevent blowing it away next time we export
        copy_tree(export_dir,helpers.EXPORTDIR + "/cdn_export")
        # Cleanup
        shutil.rmtree(helpers.EXPORTDIR + "/cdn_export/manifest", ignore_errors=True, onerror=None)
        shutil.rmtree(export_dir)

    # We're done. Write the start timestamp to file for next time
    os.chdir(script_dir)
    pickle.dump(export_times, open(vardir + '/exports_' + ename + '.pkl', "wb"))

    # And we're done!
    print helpers.GREEN + "Export complete.\n" + helpers.ENDC
    if not args.notar:
        print 'Please transfer the contents of ' + helpers.EXPORTDIR + \
            ' to your disconnected Satellite system content import location.\n' \
            'Once transferred, please run ' + helpers.BOLD + ' sat_import' \
            + helpers.ENDC + ' to extract it.'
    msg = "Export complete"
    helpers.log_msg(msg, 'INFO')

    if helpers.MAILOUT:
        helpers.tf.seek(0)
        output = "{}".format(helpers.tf.read())
        subject = "Satellite 6 export complete"
        message = "Export of " + ename + " successfully completed\n\n" + output
        helpers.mailout(subject, message)

    # Exit cleanly
    sys.exit(0)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        print >> sys.stderr, ("\n\nExiting on user cancel.")
        sys.exit(1)

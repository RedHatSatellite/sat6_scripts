#!/usr/bin/python
#title           :sat_import.py
#description     :Imports Satellite 6 Default Content View for disconnected environments
#URL             :https://github.com/ggatward/sat6_scripts
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Imports Default Org Content View exported by sat_export.py
"""

import sys, argparse, os
import simplejson as json
import helpers


def get_inputfiles(expdate):
    """
    Verify the input files exist and are valid.
    'expdate' is a date (YYYY-MM-DD) provided by the user - date is in the filename of the archive
    Returned 'basename' is the full export filename (sat6_export_YYYY-MM-DD)
    """
    basename = 'sat6_export_' + expdate
    shafile = basename + '.sha256'
    if not os.path.exists(helpers.IMPORTDIR + '/' + basename + '.sha256'):
        msg = "Cannot continue - missing sha256sum file " + helpers.IMPORTDIR + '/' + shafile
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    # Verify the checksum of each part of the import
    os.chdir(helpers.IMPORTDIR)
    msg = 'Verifying Checksums in ' + helpers.IMPORTDIR + '/' + shafile
    helpers.log_msg(msg, 'INFO')
    print msg
    result = os.system('sha256sum -c ' + shafile)

    # Return code from sha256sum is 0 if all is fine.
    if result != 0:
        msg = "Import Aborted - Tarfile checksum verification failed"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    # We're good
    msg = "Tarfile checksum verification passed"
    helpers.log_msg(msg, 'INFO')
    print helpers.GREEN + "Checksum verification - Pass" + helpers.ENDC

    return basename


def extract_content(basename):
    """
    Extract the tar archive
    """
    os.chdir(helpers.IMPORTDIR)

    # Extract the archives (Using OS call for this at the moment)
    msg = "Extracting tarfiles"
    helpers.log_msg(msg, 'INFO')
    print msg
    os.system('cat ' + basename + '_* | tar xpf -')

    #TODO: Optional delete input files
    # If successful untar:
    # rm basename + '_*'


def sync_content(org_id):
    """
    Synchronize the repositories
    Triggers a sync of all repositories belonging to the configured sync plan
    """
    # Check that the configured sync plan exists
    splans = helpers.get_json(
        helpers.KATELLO_API + "organizations/" + str(org_id) + "/sync_plans/")
    for sp_result in splans['results']:
        if sp_result['name'] == helpers.SYNCPLAN:
            sp_id = sp_result['id']
            msg = "Sync plan '" + helpers.SYNCPLAN + "' ID: " + str(sp_id)
            helpers.log_msg(msg, 'DEBUG')

    if not sp_id:
        msg = "Sync plan '" + helpers.SYNCPLAN + "' not found"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)
    else:
        # Check that no sync tasks are already running
        helpers.check_running_sync()

        msg = "No existing running or paused sync tasks detected"
        helpers.log_msg(msg, 'DEBUG')

        # Run the sync plan
        task_id = helpers.put_json(
            helpers.KATELLO_API + "organizations/" + str(org_id) + "/sync_plans/" + str(sp_id) \
                + "/sync", json.dumps(
                    {
                    }
                ))["id"]

        msg = "Sync plan started - task_id " + task_id
        helpers.log_msg(msg, 'DEBUG')

    return task_id


def main():
    """
    Main Routine
    """
    #pylint: disable-msg=R0912,R0914,R0915

    if not helpers.DISCONNECTED:
        msg = "Import cannot be run on the connected Satellite (Sync) host"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(-1)

    # Who is running this script?
    runuser = helpers.who_is_running()

    # Log the fact we are starting
    msg = "------------- Content import started by " + runuser + " ----------------"
    helpers.log_msg(msg, 'INFO')

    # Check for sane input
    parser = argparse.ArgumentParser(description='Performs Import of Default Content View.')
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization', required=True)
    parser.add_argument('-d', '--date', help='Date of Import fileset to process (YYYY-MM-DD)',
        required=True)
    parser.add_argument('-s', '--sync', help='Trigger a sync after extracting content',
        required=False, action="store_true")
    args = parser.parse_args()

    # Set our script variables from the input args
    org_name = args.org
    expdate = args.date

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Figure out if we have the specified input fileset
    basename = get_inputfiles(expdate)

    # Extract the input files
    extract_content(basename)

    # Trigger a sync of the content into the Library
    if args.sync:
        sync_content(org_id)
        print helpers.GREEN + "Import complete.\n" + helpers.ENDC
        print 'Please wait for sync to complete, then publish content views to make new' \
            'content available.'
    else:
        print helpers.GREEN + "Import complete.\n" + helpers.ENDC
        print 'Please synchronise all repositories to make new content available for publishing.'
    msg = "Import Complete"
    helpers.log_msg(msg, 'INFO')


if __name__ == "__main__":
    main()


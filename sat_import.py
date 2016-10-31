#!/usr/bin/python
#title           :sat_import.py
#description     :Imports Satellite 6 Content for disconnected environments
#URL             :https://github.com/RedHatSatellite/sat6_disconnected_tools
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Imports Satellite 6 yum content exported by sat_export.py
"""

import sys, argparse, os, pickle
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


def sync_content(org_id, imported_repos):
    """
    Synchronize the repositories
    Triggers a sync of all repositories belonging to the configured sync plan
    """
    repos_to_sync = []
    delete_override = False

    # Get a listing of repositories in this Satellite
    enabled_repos = helpers.get_p_json(
        helpers.KATELLO_API + "/repositories/", \
            json.dumps(
                {
                    "organization_id": org_id,
                    "per_page": '1000',
                }
            ))

    # Loop through each repo to be imported/synced
    for repo in imported_repos:
        do_import = False
        for repo_result in enabled_repos['results']:
            if repo in repo_result['label']:
                do_import = True
                repos_to_sync.append(repo_result['id'])

                # Ensure Mirror-on-sync flag is set to FALSE to make sure incremental
                # import does not (cannot) delete existing packages.
                msg = "Setting mirror-on-sync=false for repo id " + str(repo_result['id'])
                helpers.log_msg(msg, 'DEBUG')
                helpers.put_json(
                    helpers.KATELLO_API + "/repositories/" + str(repo_result['id']), \
                        json.dumps(
                            {
                                "mirror_on_sync": False
                            }
                        ))

        if do_import:
            msg = "Repo " + repo + " found in Satellite"
            helpers.log_msg(msg, 'DEBUG')
        else:
            msg = "Repo " + repo + " is not enabled in Satellite"
            # If the repo is not enabled, don't delete the input files.
            # This gives the admin a chance to manually enable the repo and re-import
            delete_override = True
            helpers.log_msg(msg, 'WARNING')
            # TODO: We could go on here and try to enable the Red Hat repo .....

    # If we get to here and nothing was added to repos_to_sync we will abort the import.
    # This will probably occur on the initial import - nothing will be enabled in Satellite.
    if not repos_to_sync:
        msg = "No enabled repos matching the imported content. Please enable the required repos" \
            "and sync manually."
        helpers.log_msg(msg, 'WARNING')
        sys.exit(-1)
    else:
        msg = "Repo ids to sync: " + str(repos_to_sync)
        helpers.log_msg(msg, 'DEBUG')

        msg = "Syncing repositories"
        helpers.log_msg(msg, 'INFO')
        print msg

        # Break repos_to_sync into groups of n 
        repochunks = [ repos_to_sync[i:i+helpers.SYNCBATCH] for i in range(0, len(repos_to_sync), helpers.SYNCBATCH) ]

        # Loop through the smaller batches of repos and sync them
        for chunk in repochunks:
            chunksize = len(chunk)
            msg = "Syncing repo batch " + str(chunk)
            helpers.log_msg(msg, 'DEBUG')
            task_id = helpers.post_json(
                helpers.KATELLO_API + "repositories/bulk/sync", \
                    json.dumps(
                        {
                            "ids": chunk,
                        }
                    ))["id"]
            msg = "Repo sync task id = " + task_id
            helpers.log_msg(msg, 'DEBUG')

            # Now we need to wait for the sync to complete
            helpers.wait_for_task(task_id, 'sync')

            tinfo = helpers.get_task_status(task_id)
            if tinfo['state'] != 'running' and tinfo['result'] == 'success':
                msg = "Batch of " + str(chunksize) + " repos complete"
                helpers.log_msg(msg, 'INFO')
                print helpers.GREEN + msg + helpers.ENDC
            else:
                msg = "Batch sync has errors"
                helpers.log_msg(msg, 'WARNING')

        return delete_override


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
    parser.add_argument('-d', '--date', \
        help='Date/name of Import fileset to process (YYYY-MM-DD_NAME)', required=False)
    parser.add_argument('-s', '--sync', help='Trigger an immediate sync after extracting content',
        required=False, action="store_true")
    parser.add_argument('-p', '--syncplan', help='Trigger a delayed sync via sync plan',
        required=False, action="store_true")
    parser.add_argument('-r', '--remove', help='Remove input files after import has completed',
        required=False, action="store_true")
    parser.add_argument('-l', '--last', help='Display the last successful import performed', 
        required=False, action="store_true")
    args = parser.parse_args()

    # Set our script variables from the input args
    org_name = args.org
    expdate = args.date

    # Record where we are running from
    script_dir = str(os.getcwd())

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Display the last successful import
    if args.last:
        if os.path.exists('var/imports.pkl'):
            last_import = pickle.load(open('var/imports.pkl', 'rb'))
            msg = "Last successful import was " + last_import
            helpers.log_msg(msg, 'INFO')
            print msg
        else:
            msg = "Import has never been performed"
            helpers.log_msg(msg, 'INFO')
            print msg
        sys.exit(-1)
             
    # If we got this far without -d being specified, error out cleanly
    if args.date is None:
        parser.error("--date is required")


    # Figure out if we have the specified input fileset
    basename = get_inputfiles(expdate)

    # Cleanup from any previous imports
    os.system("rm -rf " + helpers.IMPORTDIR + "/{content,custom,listing,*.pkl}")

    # Extract the input files
    extract_content(basename)

    # Trigger a sync of the content into the Library (Default action is NOT to sync)
    if args.sync:
        # We need to figure out which repos to sync. This comes to us via a pickle containing
        # a list of repositories that were exported
        imported_repos = pickle.load(open('exported_repos.pkl', 'rb'))

        # Run a repo sync on each imported repo
        (delete_override) = sync_content(org_id, imported_repos)

        print helpers.GREEN + "Import complete.\n" + helpers.ENDC
        print 'Please publish content views to make new content available.'
    if args.syncplan:
        # We can't delete the input content if we are scheduling a sync later
        delete_override = True

        msg = "Setting up sync plan"
        helpers.log_msg(msg, 'DEBUG')

        print "* * * * DO SYNC PLAN STUFF * * * *"


    else:
        print helpers.GREEN + "Import complete.\n" + helpers.ENDC
        msg = "Repository sync was requested to be skipped"
        helpers.log_msg(msg, 'WARNING')
        print 'Please synchronise all repositories to make new content available for publishing.'
        delete_override = True

    if args.remove and not delete_override:
        msg = "Removing " + helpers.IMPORTDIR + "/sat6_export_" + expdate + "* input files"
        helpers.log_msg(msg, 'DEBUG')
        os.system("rm -f " + helpers.IMPORTDIR + "/sat6_export_" + expdate) + "*"
        os.system("rm -rf " + helpers.IMPORTDIR + "/{content,custom,listing,*.pkl}")

    msg = "Import Complete"
    helpers.log_msg(msg, 'INFO')

    # Save the last completed import data
    os.chdir(script_dir)
    if not os.path.exists('var'):
        os.makedirs('var')
    pickle.dump(expdate, open('var/imports.pkl', "wb"))

if __name__ == "__main__":
    main()

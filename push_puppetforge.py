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
import helpers

try:
    import yaml
except ImportError:
    print "Please install the PyYAML module."
    sys.exit(-1)


def export_puppet(repo_id, repo_label, repo_relative, export_type):
    """
    Export Puppet modules
    Takes the type (full/incr)
    """
    numfiles = 0
    PUPEXPORTDIR = helpers.EXPORTDIR + '/puppet'
    if not os.path.exists(PUPEXPORTDIR):
        os.makedirs(PUPEXPORTDIR)

    msg = "Exporting Puppet repository id " + str(repo_id)
    helpers.log_msg(msg, 'INFO')

    # This will currently export ALL ISO, not just the selected repo
    msg = "Exporting all Puppet content"
    helpers.log_msg(msg, 'INFO')

    msg = "  Copying files for export..."
    colx = "{:<70}".format(msg)
    print colx[:70],
    helpers.log_msg(msg, 'INFO')
    # Force the status message to be shown to the user
    sys.stdout.flush()

    os.system('find -L /var/lib/pulp/published/puppet/http/repos/*' + repo_label \
        + ' -type f -exec cp --parents -Lrp {} ' + PUPEXPORTDIR + ' \;')

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

                    # Since we are dealing with Puppet_Forge, create a second bundle for import to puppet-forge-server
                    if 'Puppet_Forge' in OUTDIR:
                        PFEXPORTDIR = helpers.EXPORTDIR + '/puppetforge'
                        if not os.path.exists(PFEXPORTDIR):
                            os.makedirs(PFEXPORTDIR)
                        os.system('find ' + OUTDIR + ' -name "*.gz" -exec cp {} ' + PFEXPORTDIR + ' \;')

                    msg = 'Puppet Export OK (' + str(numfiles) + ' files)'
                    helpers.log_msg(msg, 'INFO')
                    print helpers.GREEN + msg + helpers.ENDC

    # Now we are done with the original export dumps, we can delete them.
    shutil.rmtree(helpers.EXPORTDIR + '/export')
    shutil.rmtree(helpers.EXPORTDIR + '/puppet')

    return numfiles


def copy_to_pfserver(export_dir, pfserver, pfmodpath, pfuser):
    """
    Use rsync to copy the exported module tree to the puppet-forge-server instance
    """
    target = pfuser + '@' + pfserver + ':' + pfmodpath
    msg = 'Copying puppet modules to ' + target + '\n'
    helpers.log_msg(msg, 'INFO')
    print msg
    os.system('rsync -avrzc ' + export_dir + '/* ' + target)


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
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization (Uses default if not specified)',
        required=False)
    parser.add_argument('-r', '--repo', help='Puppetforge repo label', required=False)
    parser.add_argument('-s', '--server', help='puppet-forge-server hostname', required=False)
    parser.add_argument('-m', '--modulepath', help='path to puppet-forge-server modules', 
        required=False)
    parser.add_argument('-u', '--user', help='Username to push modules to server as (default is user running script)', 
        required=False)
    args = parser.parse_args()

    # Set our script variables from the input args
    if args.org:
        org_name = args.org
    else:
       org_name = helpers.ORG_NAME

    # Define the puppet-forge-server hostname
    if args.server:
        pfserver = args.server
    else:
        if not helpers.PFSERVER:
            print "Puppet forge server not defined"
            sys.exit(-1)
        else:
            pfserver = helpers.PFSERVER

    # Set the remote (puppet-forge-server) modules directory
    if args.modulepath:
        modpath = args.modulepath
    else:
        modpath = '/opt/puppetforge/modules'

    # Set the username to use to push modules
    if args.user:
        pfuser = args.user
    else:
        pfuser = runuser

    # Record where we are running from
    script_dir = str(os.getcwd())

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Read the repo label given by the user
    if args.repo:
        pfrepo = args.repo
    else:
        print "Puppetforge repo not defined"
        sys.exit(-1)

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


    # Process each repo
    for repo_result in repolist['results']:
        if repo_result['content_type'] == 'puppet':
            # If we have a match, do the export
            if repo_result['label'] == pfrepo:

                # Trigger export on the repo
                numfiles = export_puppet(repo_result['id'], repo_result['label'], repo_result['relative_path'], 'full')

            else:
                msg = "Skipping  " + repo_result['label']
                helpers.log_msg(msg, 'DEBUG')


    # Now we need to process the on-disk export data.
    # Define the location of our exported data.
    export_dir = helpers.EXPORTDIR + "/puppetforge"

    # Now we can copy the content to the puppet-forge-server instance
    os.chdir(script_dir)
    copy_to_pfserver(export_dir, pfserver, modpath, pfuser)


    # And we're done!
    print helpers.GREEN + "Puppet Forge export complete.\n" + helpers.ENDC


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        print >> sys.stderr, ("\n\nExiting on user cancel.")
        sys.exit(1)

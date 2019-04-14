#!/usr/bin/python
#title           :clean_content_views.py
#description     :Removes orphaned versions of Satellite 6 content views
#URL             :https://github.com/ggatward/sat6_scripts
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Removes content view versions that don't belong to any environment

"""
#pylint: disable-msg=R0912,R0913,R0914,R0915

import sys, argparse
import collections
import simplejson as json
import helpers

def get_cv(org_id, cleanup_list, keep):
    """Get the content views"""

    # Query API to get all content views for our org
    cvs = helpers.get_json(
        helpers.KATELLO_API + "organizations/" + str(org_id) + "/content_views/")
    ver_list = collections.OrderedDict()
    ver_descr = collections.OrderedDict()
    ver_keep = collections.OrderedDict()

    # Sort the CVS so that composites are considered first
    cv_results = sorted(cvs['results'], key=lambda k: k[u'composite'], reverse=True)

    for cv_result in cv_results:
        # We will never clean the DOV
        if cv_result['name'] != "Default Organization View":
            # Handle specific includes
            if cleanup_list:
                # The list contains dictionaries as elements. Process each dictionary
                for cv in cleanup_list:
                    # If the CV name does not appear in our config list, skip
                    if cv['view'] != cv_result['name']:
                        msg = "Skipping " + cv_result['name']
                        helpers.log_msg(msg, 'DEBUG')
                        continue
                    else:
                        msg = "Processing content view '" + cv_result['name'] + "' " \
                            + str(cv_result['id'])
                        helpers.log_msg(msg, 'DEBUG')

                        # Add the next version of the view, and how many versions to keep
                        ver_list[cv_result['id']] = cv_result['id']
                        ver_descr[cv_result['id']] = cv_result['name']
                        ver_keep[cv_result['id']] = cv['keep']

            # Handle the 'all' option
            else:
                msg = "Processing content view '" + cv_result['name'] + "' " \
                    + str(cv_result['id'])
                helpers.log_msg(msg, 'DEBUG')

                # Add the next version of the view, and how many versions to keep
                ver_list[cv_result['id']] = cv_result['id']
                ver_descr[cv_result['id']] = cv_result['name']
                ver_keep[cv_result['id']] = keep


    return ver_list, ver_descr, ver_keep


def get_content_view_info(cvid):
    """
    Return Content View Info for a given CV ID
    """
    cvinfo = helpers.get_json(
        helpers.KATELLO_API + "content_views/" + str(cvid))

    return cvinfo


def check_version_views(version_id):
    """
    Check if our version ID belongs to any views, including CCV
    """
    version_in_use = False
    version_in_ccv = False

    # Extract a list of content views that the CV version belongs to
    viewlist = helpers.get_json(
        helpers.KATELLO_API + "content_view_versions/" + str(version_id))

    # If the list is not empty we need to return this fact. A CV that belongs
    # to NO versions will be a candidate for cleanup.
    viewlist['composite_content_view_ids']
    if viewlist['katello_content_views']:
        version_in_use = True
        msg = "Version " + str(viewlist['version']) + " is associated with published CV"
        helpers.log_msg(msg, 'DEBUG')

        # We can go further and see if this is associated with a CCV
        if viewlist['composite_content_view_ids']:
            version_in_ccv = True

    return version_in_use, version_in_ccv


def cleanup(ver_list, ver_descr, dry_run, runuser, ver_keep, cleanall, ignorefirstpromoted):
    """Clean Content Views"""

    # Set the task name to be displayed in the task monitoring stage
    task_name = "Cleanup content views"

    # Now we have all the info needed, we can actually trigger the cleanup.
    task_list = []
    ref_list = {}

    # Catch scenario that no CV versions are found matching cleanup criteria
    if not ver_list:
        msg = "No content view versions found matching cleanup criteria"
        helpers.log_msg(msg, 'ERROR')
        sys.exit(1)

    for cvid in ver_list.keys():
        msg = "Cleaning content view '" + str(ver_descr[cvid]) + "'"
        helpers.log_msg(msg, 'INFO')
        print helpers.HEADER + msg + helpers.ENDC

        # Check if there is a publish/promote already running on this content view
        locked = helpers.check_running_publish(ver_list[cvid], ver_descr[cvid])
        if locked:
            continue

        # For the given content view we need to find the orphaned versions
        cvinfo = get_content_view_info(cvid)

        # Find the oldest published version
        version_list = []
        orphan_versions = []
        orphan_dict = {}
        all_versions = []
        ccv_versions = []
        for version in cvinfo['versions']:

            # Check if the version is part of a published view.
            # This is not returned in cvinfo, and we need to see if we are part of a CCV
            version_in_use, version_in_ccv = check_version_views(version['id'])

            # Build a list of ALL version numbers
            all_versions.append(float(version['version']))
            # Add any version numbers that are part of a CCV to a list
            if version_in_ccv:
                ccv_versions.append(float(version['version']))
            if not version['environment_ids']:
                # These are the versions that don't belong to an environment (i.e. orphans)
                # We also cross-check for versions that may be in a CCV here.
                # We add the version name and id into a dictionary so we can delete by id.
                if not version_in_use:
                    orphan_versions.append(float(version['version']))
                    orphan_dict[version['version']] = version['id']
                    continue
            else:
                msg = "Found version " + str(version['version'])
                helpers.log_msg(msg, 'DEBUG')
                # Add the version id to a list
                version_list.append(float(version['version']))

        # Find the oldest 'in use' version id
        if not version_list:
            msg = "No oldest in-use version found"
        else:
            lastver = min(version_list)
            msg = "Oldest in-use version is " + str(lastver)
        helpers.log_msg(msg, 'DEBUG')

        # Find the oldest 'NOT in use' version id
        if not orphan_versions:
            msg = "No oldest NOT-in-use version found"
        else:
            msg = "Oldest NOT-in-use version is " + str(min(orphan_versions))
        helpers.log_msg(msg, 'DEBUG')

        # Find the element position in the all_versions list of the oldest in-use version
        # e.g. vers 102.0 is oldest in-use and is element [5] in the all_versions list
        list_position = [i for i,x in enumerate(all_versions) if x == lastver]
        # Remove the number of views to keep from the element position of the oldest in-use
        # e.g. keep=2 results in an adjusted list element position [3]
        num_to_delete = list_position[0] - int(ver_keep[cvid])
        # Delete from position [0] to the first 'keep' position
        # e.g. first keep element is [3] so list of elements [0, 1, 2] is created
        list_pos_to_delete = [i for i in range(num_to_delete)]

        # Find versions to delete (based on keep parameter)
        # Make sure the version list is in order
        orphan_versions.sort()

        if cleanall:
            # Remove all orphaned versions
            todelete = orphan_versions
        elif ignorefirstpromoted:
            # Remove the last 'keep' elements from the orphans list (from PR #26)
            todelete = orphan_versions[:(len(orphan_versions) - int(ver_keep[cvid]))]
        else:
            todelete = []
            # Remove the element numbers for deletion from the list all versions
            for i in sorted(list_pos_to_delete, reverse=True):
                todelete.append(orphan_versions[i])

        msg = "Versions to remove: " + str(todelete)
        helpers.log_msg(msg, 'DEBUG')

        for version in all_versions:
            if not locked:
                if version in todelete:
                    msg = "Orphan view version " + str(version) + " found in '" +\
                        str(ver_descr[cvid]) + "'"
                    helpers.log_msg(msg, 'DEBUG')

                    # Lookup the version_id from our orphan_dict
                    delete_id = orphan_dict.get(str(version))

                    msg = "Removing version " + str(version)
                    helpers.log_msg(msg, 'INFO')
                    print helpers.HEADER + msg + helpers.ENDC
                else:
                    if version in ccv_versions:
                        msg = "Skipping delete of version " + str(version) + " (member of a CCV)"
                    elif version in orphan_versions:
                        msg = "Skipping delete of version " + str(version) + " (due to keep value)"
                    else:
                        msg = "Skipping delete of version " + str(version) + " (in use)"
                    helpers.log_msg(msg, 'INFO')
                    print msg
                    continue
            else:
                msg = "Version " + str(version) + " is locked"
                helpers.log_msg(msg, 'WARNING')
                continue

            # Delete the view version from the content view
            if not dry_run and not locked:
                try:
                    task_id = helpers.put_json(
                        helpers.KATELLO_API + "content_views/" + str(cvid) + "/remove/",
                        json.dumps(
                            {
                                "id": cvid,
                                "content_view_version_ids": delete_id
                            }
                            ))['id']

                    # Wait for the task to complete
                    helpers.wait_for_task(task_id,'clean')

                    # Check if the deletion completed successfully
                    tinfo = helpers.get_task_status(task_id)
                    if tinfo['state'] != 'running' and tinfo['result'] == 'success':
                        msg = "Removal of content view version OK"
                        helpers.log_msg(msg, 'INFO')
                        print helpers.GREEN + "OK" + helpers.ENDC
                    else:
                        msg = "Failed"
                        helpers.log_msg(msg, 'ERROR')

                except Warning:
                    msg = "Failed to initiate removal"
                    helpers.log_msg(msg, 'WARNING')

                except KeyError:
                    msg = "Failed to initiate removal (KeyError)"
                    helpers.log_msg(msg, 'WARNING')

    # Exit in the case of a dry-run
    if dry_run:
        msg = "Dry run - not actually performing removal"
        helpers.log_msg(msg, 'WARNING')
        sys.exit(2)


def main(args):
    """
    Main routine
    """

    # Who is running this script?
    runuser = helpers.who_is_running()

    # Check for sane input
    parser = argparse.ArgumentParser(
        description='Cleans content views for specified organization.')
    group = parser.add_mutually_exclusive_group()
    # pylint: disable=bad-continuation
    parser.add_argument('-o', '--org', help='Organization (Uses default if not specified)',
        required=False)
    parser.add_argument('-k', '--keep', help='How many old versions to keep (only used with -a)',
        required=False)
    group.add_argument('-a', '--all', help='Clean ALL content views', required=False,
        action="store_true")
    parser.add_argument('-c', '--cleanall', help='Remove orphan versions between in-use views',
        required=False, action="store_true")
    parser.add_argument('-i', '--ignorefirstpromoted', help='Version to keep count starts from first CV, not first promoted CV',
        required=False, action="store_true")
    parser.add_argument('-d', '--dryrun', help='Dry Run - Only show what will be cleaned',
        required=False, action="store_true")

    args = parser.parse_args()

    # Log the fact we are starting
    msg = "-------- Content view cleanup started by " + runuser + " -----------"
    helpers.log_msg(msg, 'INFO')

    # Set our script variables from the input args
    if args.org:
        org_name = args.org
    else:
       org_name = helpers.ORG_NAME
    dry_run = args.dryrun
    cleanall = args.cleanall
    ignorefirstpromoted = args.ignorefirstpromoted
    if args.keep:
        keep = args.keep
    else:
        keep = "0"

    cleanup_list = []
    if not args.all:
        cleanup_list = helpers.CONFIG['cleanup']['content_views']

        if not cleanup_list:
            msg = "Cannot find cleanup configuration"
            helpers.log_msg(msg, 'ERROR')
            sys.exit(1)

        msg = "Config found for CV's " + str(cleanup_list)
        helpers.log_msg(msg, 'DEBUG')

    # Get the org_id (Validates our connection to the API)
    org_id = helpers.get_org_id(org_name)

    # Get the list of Content Views along with the latest view version in each environment
    (ver_list, ver_descr, ver_keep) = get_cv(org_id, cleanup_list, keep)

    # Clean the content views. Returns a list of task IDs.
    cleanup(ver_list, ver_descr, dry_run, runuser, ver_keep, cleanall, ignorefirstpromoted)

    # Exit cleanly
    sys.exit(0)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        print >> sys.stderr, ("\n\nExiting on user cancel.")
        sys.exit(1)

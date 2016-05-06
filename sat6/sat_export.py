#!/usr/bin/python
"""
Exports Default Org Content View.

NOTE:  This file is managed by the STASH git repository. Any modifications to
       this file must be made in the source repository and then deployed.
"""

import sys, argparse, datetime
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
    """Main Routine"""
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

    # Get the last export date. If we're exporting all, this isn't relevant.
    # If we are given a start date, use that, otherwise we need to get the last date from file.
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


    # Get the version of the CV (Default Org View) to export
    dov_ver = get_cv(org_id)
    print "DOV ver = " + str(dov_ver)


    # Now we have a CV ID we can run the export.


    # We're done. Write the start timestamp to file for next time.
#    write_timestamp(start_time)


if __name__ == "__main__":
    main()


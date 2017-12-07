#!/usr/bin/env python

import sys, os, glob
import subprocess
import argparse
import helpers


def run_imports(dryrun):
    print "Processing Imports..."

    # Find any sha256 files in the import dir
    infiles = glob.glob(helpers.IMPORTDIR + '/*.sha256')

    # Extract the dataset timestamp/name from the filename and add to a new list
    # Assumes naming standard   sat6_export_YYYYMMDD-HHMM_NAME.sha256
    # 'sorted' function should result in imports being done in correct order by filename
    tslist = []
    for f in sorted(infiles):
        dstime = f.split('_')[-2]
        dsname = (f.split('_')[-1]).split('.')[-2]
        tslist.append(dstime + '_' + dsname)

    if tslist:
        msg = 'Found import datasets on disk...\n' + '\n'.join(tslist)
    else:
        msg = 'No import datasets to process'
    helpers.log_msg(msg, 'INFO')
    print msg

    # Now for each import file in the list, run the import script in unattended mode:-)
    if tslist:
        if not dryrun:
            for dataset in tslist:
                rc = subprocess.call(['/usr/local/bin/sat_import', '-u', '-r', '-d', dataset])
                print rc
        else:
            msg = "Dry run - not actually performing import"
            helpers.log_msg(msg, 'WARNING')


def main(args):

    ### Run import/publish on scheduled day

    # Check for sane input
    parser = argparse.ArgumentParser(
        description='Imports, Publishes and Promotes content views.')
    parser.add_argument('-d', '--dryrun', help='Dry Run - Only show what will be done',
        required=False, action="store_true")

    args = parser.parse_args()

    if args.dryrun:
        dryrun = True
    else:
        dryrun = False


    # Check if there are any imports in our input dir and import them
    run_imports(dryrun)

    # If all imports successful run publish


    ### Run promote on scheduled display



    ### Run cleanup on scheduled day






if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        print >> sys.stderr, ("\n\nExiting on user cancel.")
        sys.exit(1)

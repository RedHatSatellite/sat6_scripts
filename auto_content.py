#!/usr/bin/env python

import sys, os, glob
import subprocess
import argparse
import datetime
import helpers


def dates():
    # What day is it?  (0=Mon -> 6=Sun)
    dayofweek = datetime.datetime.today().weekday()

    # Figure out which week of the month we are in
    weekofmonth = (datetime.datetime.now().day-1)/7+1

    print "Day %s of week %s" % (dayofweek, weekofmonth)

    return(dayofweek,weekofmonth)


def run_imports(dryrun):
    print "Processing Imports..."

    # Find any sha256 files in the import dir
    infiles = glob.glob(helpers.IMPORTDIR + '/*.sha256')

    # Extract the dataset timestamp/name from the filename and add to a new list
    # Assumes naming standard   sat6_export_YYYYMMDD-HHMM_NAME.sha256
    # 'sorted' function should result in imports being done in correct order by filename
    tslist = []
    good_imports = False
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

                # If the import is successful
                if rc == 0:
                    good_imports = True

        else:
            msg = "Dry run - not actually performing import"
            helpers.log_msg(msg, 'WARNING')

    return good_imports


def publish_cv(dryrun):
    print "Running Content View Publish..."

    # Set the initial state
    good_publish = False

    if not dryrun:
        rc = subprocess.call(['/usr/local/bin/publish_content_views', '-q', '-a'])
    else:
        msg = "Dry run - not actually performing publish"
        helpers.log_msg(msg, 'WARNING')
        rc = subprocess.call(['/usr/local/bin/publish_content_views', '-q', '-a', '-d'])

    if rc == 0:
        good_publish = True

    return good_publish


def promote_cv(dryrun, lifecycle):
    print "Running Content View Promotion to " + lifecycle + "..."

    # Set the initial state
    good_promote = False

    if not dryrun:
        rc = subprocess.call(['/usr/local/bin/promote_content_views', '-q', '-e', lifecycle])
    else:
        msg = "Dry run - not actually performing promotion"
        helpers.log_msg(msg, 'WARNING')
        rc = subprocess.call(['/usr/local/bin/promote_content_views', '-q', '-d', '-e', lifecycle])

    if rc == 0:
        good_promote = True

    return good_promote


def push_puppet(dryrun):
    print "Pushing puppet modules to puppet-forge server..."

    # Set the initial state
    good_puppetpush = False

    if not dryrun:
        for dataset in tslist:
            rc = subprocess.call(['/usr/local/bin/push-puppetforge', '-r', 'puppet-forge'])

            # If the import is successful
            if rc == 0:
                good_puppetpush = True

    else:
        msg = "Dry run - not actually performing module push"
        helpers.log_msg(msg, 'WARNING')

    return good_puppetpush


def clean_cv(dryrun):
    print "Running Content View Cleanup..."

    if not dryrun:
        rc = subprocess.call(['/usr/local/bin/clean_content_views', '-a', '-c'])
    else:
        msg = "Dry run - not actually performing cleanup"
        helpers.log_msg(msg, 'WARNING')
        rc = subprocess.call(['/usr/local/bin/clean_content_views', '-a', '-c', '-d'])


def main(args):

    ### Run import/publish on scheduled day

    # Check for sane input
    parser = argparse.ArgumentParser(
        description='Imports, Publishes and Promotes content views.')
    parser.add_argument('-d', '--dryrun', help='Dry Run - Only show what will be done',
        required=False, action="store_true")
    parser.add_argument('-p', '--puppet', help='Include puppet-forge module push',
        required=False, action="store_true")

    args = parser.parse_args()

    # Set default flags and read in options given to us
    if args.dryrun:
        dryrun = True
    else:
        dryrun = False

    run_publish = False
    run_promote = True

    # Determine the day of week and week of month for use in our scheduling
    (dayofweek, weekofmonth) = dates()


    # Run promotion first - this ensures content consistency (QA->Prod, Library->QA)
    if dayofweek == 0:
        if weekofmonth == 4:
            run_promote = promote_cv(dryrun, 'Production')

        # Run QA promotion on 2nd and 4th Monday. Conditional on Prod promotion success
        if weekofmonth == 2 or weekofmonth == 4:
            if run_promote:
                run_promote = promote_cv(dryrun, 'Quality')


    # Every day, check if there are any imports in our input dir and import them.
    # run_publish will be returned as 'True' if any successful imports were performed.
    # If no imports are performed, or they fail, publish can't be triggered.
    run_publish = run_imports(dryrun)

    # If the imports succeeded, we can go ahead and publish the new content to Library
    if run_publish:
        publish_cv(dryrun)
        # Push any new puppet-forge modules if we have requested that
        if args.puppet:
            push_puppet(dryrun)

    # Run content view cleanup once a month, after we have done all promotions for the month.
    if dayofweek == 3:
        if weekofmonth == 4:
            clean_cv(dryrun)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        print >> sys.stderr, ("\n\nExiting on user cancel.")
        sys.exit(1)

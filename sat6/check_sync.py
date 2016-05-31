#!/usr/bin/python
#title           :check_sync.py
#description     :Checks Satellite 6 repository sync status
#URL             :https://github.com/ggatward/sat6_scripts
#author          :Geoff Gatward <ggatward@redhat.com>
#notes           :This script is NOT SUPPORTED by Red Hat Global Support Services.
#license         :GPLv3
#==============================================================================
"""
Checks the status of Sync tasks.
Draws the users attention to problems in the sync tasks that could lead to
inconsistent repository states.

Call with -l switch to loop until all sync tasks are complete, otherwise runs
as a one-shot check.
"""

import sys, os, argparse, time
import helpers


def check_running_tasks(clear):
    """
    Check for any currently running Sync tasks
    Checks for any Synchronize tasks in running/paused or Incomplete state.
    """
    #pylint: disable-msg=R0912,R0914,R0915
    # Clear the screen
    if clear:
        os.system('clear')

    print helpers.HEADER + "Checking for running/paused yum sync tasks..." + helpers.ENDC
    tasks = helpers.get_json(
        helpers.FOREMAN_API + "tasks/")

    # From the list of tasks, look for any running export or sync jobs.
    # If e have any we exit, as we can't export in this state.
    running_sync = 0
    for task_result in tasks['results']:
        if task_result['state'] == 'running' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Synchronize':
                running_sync = 1
                print helpers.BOLD + "Running: " + helpers.ENDC + task_result['input']['repository']['name']
        if task_result['state'] == 'paused' and task_result['label'] != 'Actions::BulkAction':
            if task_result['humanized']['action'] == 'Synchronize':
                running_sync = 1
                print helpers.ERROR + "Paused:  " + helpers.ENDC + task_result['input']['repository']['name']

    if not running_sync:
        print helpers.GREEN + "None detected" + helpers.ENDC


    # Check any repos marked as Sync Incomplete
    print helpers.HEADER + "\nChecking for incomplete (stopped) yum sync tasks..." + helpers.ENDC
    repo_list = helpers.get_json(
        helpers.KATELLO_API + "/content_view_versions")

    # Extract the list of repo ids, then check the state of each one.
    incomplete_sync = 0
    for repo in repo_list['results']:
        for repo_id in repo['repositories']:
            repo_status = helpers.get_json(
                helpers.KATELLO_API + "/repositories/" + str(repo_id['id']))

            if repo_status['content_type'] == 'yum':
                if repo_status['last_sync'] is None:
                    if repo_status['library_instance_id'] is None:
                        incomplete_sync = 1
                        print helpers.ERROR + "Broken Repo: " + helpers.ENDC + repo_status['name']
                elif repo_status['last_sync']['state'] == 'stopped':
                    if repo_status['last_sync']['result'] == 'warning':
                        incomplete_sync = 1
                        print helpers.WARNING + "Incomplete: " + helpers.ENDC + repo_status['name']

    # If we have detected incomplete sync tasks, ask the user if they want to export anyway.
    # This isn't fatal, but *MAY* lead to inconsistent repositories on the dieconnected sat.
    if not incomplete_sync:
        print helpers.GREEN + "None detected\n" + helpers.ENDC
    else:
        print "\n"

    # Exit the loop if both tests are clear
    if not running_sync and not incomplete_sync:
        sys.exit(-1)


def main():
    """
    Main Routine
    """
    #pylint: disable-msg=R0914,R0915

    parser = argparse.ArgumentParser(description='Checks status of yum repository sync tasks.')
    # pylint: disable=bad-continuation
    parser.add_argument('-l', '--loop', help='Loop check until all tasks complete', required=False,
            action="store_true")
    args = parser.parse_args()


    # Check if there are any currently running tasks that will conflict with an export
    # Loop until all tasks are compltete.
    if args.loop:
        try:
            while True:
                clear = True
                check_running_tasks(clear)
                time.sleep(5)
        except KeyboardInterrupt:
            print "End"

    else:
        clear = False
        check_running_tasks(clear)

if __name__ == "__main__":
    main()


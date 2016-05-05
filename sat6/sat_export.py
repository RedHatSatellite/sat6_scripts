#!/usr/bin/python
"""
Exports Default Org Content View.

NOTE:  This file is managed by the STASH git repository. Any modifications to
       this file must be made in the source repository and then deployed.
"""

import sys, argparse
from time import sleep
import helpers




def main():
    """Main Routine"""
    # Log the fact we are starting
    msg = "------------- Content export started by ..user.. ----------------"
    helpers.log_msg(msg, 'INFO')

    # Check for sane input
    parser = argparse.ArgumentParser(description='Performs Export of Default Content View.')
    parser.add_argument('-o', '--org', help='Organization', required=True)
    args = parser.parse_args()

    # Set our script variables from the input args
    org_name = args.org

    # Get the org_id
    org_id = helpers.get_org_id(org_name)

    print org_id


if __name__ == "__main__":
    main()


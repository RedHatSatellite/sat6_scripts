#!/bin/sh

# Placeholder script until python version written

# requires satellite root ssh pubkey pushed to forge@puppet-forge-server


PFSERVER=$1

if [ $# -ne 1 ]; then
  echo "Please specify the puppet-forge server hostname"
  exit 1
fi

scp /var/sat-content/puppetforge/*.gz forge@$PFSERVER:/opt/puppetforge/modules
#ssh forge@$PFSERVER chown -R forge:forge /opt/puppetforge/modules
#ssh forge@$PFSERVER restorecon -R /opt/puppetforge/modules


# sat6_scripts
Scripts to automate various Satellite 6 tasks.

These scripts have been written and tested using Satellite 6.2 Beta on RHEL7


## Definitions
Throughout these scripts the following references are used:
- Connected Satellite: Internet connection is available
- Disconnected Satellite: No internet connection is available
- Sync Host: Connected Satellite that downloads and exports content for a Disconnected Satellite


## Requirements
The Export and Import scripts are intended to be run on the Satellite servers directly.
- sat_export is intended to run on the Connected Satellite,
- sat_import is intended to run on the Disconnected Satellite.
Other scripts may be run from the Satellite server or from a management host.

* You will need to install PyYAML to use these scripts.
`yum -y install PyYAML`

* The scripts make use of the Satellite REST API, and require an admin account on the Satellite server.
```
hammer user create --login svc-api --firstname API --lastname User --password='AP1Us3r' \
  --mail no-reply@example.org --auth-source-id 1 --organization-ids 1 --default-organization-id 1 \
  --timezone 'Canberra' --admin true
```


## Assumptions
For content import to a disconnected Satellite, it is assumed that the relevant
subscription manifest has been uploaded on the disconnected satellite. For the
_import with sync_ option, the repositories on the disconnected satellite must
have already been enabled and added to the import sync plan.


## Configuration
A YAML based configuration file is in config/config.yml.example  
The example file needs to be copied to config/config.yml and customised as
required:

```
satellite:
  url: https://*FQDN of Satellite Server*
  username: *API Username*
  password: *API user password*
  disconnected: *Is direct internet connection available* (True|False)

logging:
  dir: *Directory to use for logging*
  debug: False  

export:
  dir: *Directory to export content to (Connected Satellite)*

import:
  dir: *Directory to import content from (Disconnected Satellite)*
  syncplan: *Name of sync plan triggered after content import*
```

## Scripts in this project

- **check_sync**
A quick method to check the status of sync tasks from the command line.
Will show any sync tasks that have stuck in a 'paused' state, as well as any
tasks that have stopped but been marked as Incomplete.
Running with the -l flag will loop the check until terminated with CTRL-C


- **sat_export**
Intended to perform content export from a Connected Satellite (Sync Host), for
transfer into a disconnected environment. The Default Organization View (DOV)
is exported, meaning that there is no specific requirement to create lifecycle
environments or Content Views on the sync host.
The following export types can be performed:
    - A full export (-a)
    - An incremental export of content since the last successful export (-i)
    - An incremental export of content from a given date (-s)

For all exports, the exported RPMs are verified for GPG integrity before being
added to a chunked tar archive, with each part of the archive being sha256sum'd
for cross domain transfer integrity checking.

```
usage: sat_export.py [-h] -o ORG [-a | -i | -s SINCE] [-l]

Performs Export of Default Content View.

optional arguments:
  -h, --help            show this help message and exit
  -o ORG, --org ORG     Organization
  -a, --all             Export ALL content
  -i, --incr            Incremental Export of content since last run
  -s SINCE, --since SINCE
                        Export content since YYYY-MM-DD HH:MM:SS
  -l, --last            Display time of last export

```

- **sat_import**
This companion script to sat_export, running on the Disconnected Satellite
performs a sha256sum verification of each part of the specified archive prior
to extracting the transferred content to disk.

Once the content has been extracted, a sync can be triggered (-s) of all
repositories belonging to a sync plan, defined in the config.yml

```
usage: sat_import.py [-h] -o ORG -d DATE [-s]

Performs Import of Default Content View.

optional arguments:
  -h, --help            show this help message and exit
  -o ORG, --org ORG     Organization
  -d DATE, --date DATE  Date of Import fileset to process (YYYY-MM-DD)
  -s, --sync            Trigger a sync after extracting content
```

- **clean_content_views**
This script removes orphaned versions of either all or nominated content views.
This should be run periodically to clean out old/unused content view data from
the mongo database and improve the responsiveness of the Satellite server.

To target a specific content view, the *name* of the content view must be given
in quotes. (e.g. ./clean_content_view -v 'RHEL Server')

```

```

# Overview

Importing content in a disconnected environment can be a challenge. 
These scripts make use of the Inter-Satellite Sync capability in Satellite 6.2 to
allow for full and incremental export/import of content between environments. 

These scripts have been written and tested using Satellite 6.2 on RHEL7

## Definitions
Throughout these scripts the following references are used:
* Connected Satellite: Internet connection is available
* Disconnected Satellite: No internet connection is available
* Sync Host: Connected Satellite that downloads and exports content for a Disconnected Satellite


# Requirements
* Satellite >= 6.2.x
* Python >= 2.7
* PyYAML

The Export and Import scripts are intended to be run on the Satellite servers directly.
* sat_export is intended to run on the Connected Satellite,
* sat_import is intended to run on the Disconnected Satellite.
* The scripts make use of the Satellite REST API, and require an admin account on the Satellite server.
```
hammer user create --login svc-api-user --firstname API --lastname User \
  --password='1t$a$3cr3t' --mail no-reply@example.org --auth-source-id 1 \
  --organization-ids 1 --default-organization-id 1 --admin true
```

## Assumptions
For content import to a disconnected Satellite, it is assumed that the relevant
subscription manifest has been copied to and uploaded in the disconnected satellite. 
For the _import with sync_ option (default), required Red Hat repositories on the 
disconnected satellite must have already been enabled, and any custom repositories created.

For custom repos, the names of the product and the repositories within __MUST__ match on
both the connected and disconnected Satellites.


## Configuration
A YAML based configuration file is in config/config.yml.example  
The example file needs to be copied to config/config.yml and customised as
required:

```
satellite:
  url: https://sat6.example.org
  username: svc-api-user
  password: 1t$a$3cr3t
  disconnected: [True|False]     (Is direct internet connection available?)
  default_org: MyOrg             (Default org to use - can be overridden with -o)

logging:
  dir: /var/log/sat6-scripts     (Directory to use for logging)
  debug: [True|False]

export:
  dir: /var/sat-export           (Directory to export content to - Connected Satellite)

import:
  dir: /var/sat-content          (Directory to import content from - Disconnected Satellite)
  syncbatch: 50                  (Number of repositories to sync at once during import)
```

## Log files
The scripts in this project will write output to satellite.log in the directory
specified in the config file.


## Scripts in this project

# check_sync
A quick method to check the status of sync tasks from the command line.
Will show any sync tasks that have stuck in a 'paused' state, as well as any
tasks that have stopped but been marked as Incomplete.
Running with the -l flag will loop the check until terminated with CTRL-C


# sat_export
Intended to perform content export from a Connected Satellite (Sync Host), for
transfer into a disconnected environment. The Default Organization View (DOV)
is exported by default, meaning that there is no specific requirement to create
lifecycle environments or Content Views on the sync host. If there is a requirement
to export only certain repositories, this can also be specified using additional
configuration files. The following export types can be performed:
    * A full export (-a)
    * An incremental export of content since the last successful export (-i)
    * An incremental export of content from a given date (-s)
    * Export of a limited repository set (-e) defined by config file (see below)

By default, the exported RPMs are verified for GPG integrity before being
added to a chunked tar archive, with each part of the archive being sha256sum'd
for cross domain transfer integrity checking. 

The GPG check requires that GPG keys are imported into the local RPM GPG store.
The RPM GPG keys must be insalled on the connected satellite.
```
rpm --import <gpg-key>
```

If there is a need to NOT perform the GPG check of the exported packages, the 
GPG check can be skipped using the (-n) option.

For each export performed, a log of all RPM packages that are exported is kept
in the configured log directory. This has been found to be a useful tool to see
when (or if) a specific package has been imported into the disconnected host.

Satellite will export the repodata of all included repositories, even if the
repo has no content to export. The way the sat_import script works is that it will
perform a sync on these 'empty' repos, consuming time and resources, especially if
multiple capsules are then synced as well. By default, 'empty' repos are not included
for import sync, however this behaviour can be overridden with the (-r) flag. This 
will be useful to periodically ensure that the disconnected satellite repos are 
consistent - the repodata will indicate mismatches with synced content.

To export a selected repository set, the exports.yml config file must exist in the 
config directory. The format of this file is shown below, and contains one or more
'env' stanzas, containing a list of repositories to export. The repository name is
the LABEL taken from the Satellite server.

Note also that the 'environment' export option also allows for the export of ISO
(file) based repositories in addition to yum RPM content. Using the DOV export does
NOT include ISO repos, as export of these type of repositories is not supported by
the current pulp version in Satellite. The 'environment' export performs some 
additional magic to export the file content.

```
exports:
  env1:
    name: DEVELOPMENT
    repos:
      - Red_Hat_Satellite_6_2_for_RHEL_7_Server_RPMs_x86_64
      - Red_Hat_Satellite_Tools_6_2_for_RHEL_7_Server_RPMs_x86_64
      - Red_Hat_Enterprise_Linux_7_Server_Kickstart_x86_64_7_3
      - Red_Hat_Enterprise_Linux_7_Server_RPMs_x86_64_7Server
      - Red_Hat_Enterprise_Linux_7_Server_-_Extras_RPMs_x86_64
      - Red_Hat_Enterprise_Linux_7_Server_-_Optional_RPMs_x86_64_7Server
      - Red_Hat_Enterprise_Linux_7_Server_-_RH_Common_RPMs_x86_64_7Server
      - Red_Hat_Software_Collections_RPMs_for_Red_Hat_Enterprise_Linux_7_Server_x86_64_7Server
      - Red_Hat_Enterprise_Linux_7_Server_ISOs_x86_64_7Server
      - epel-7-x86_64

  env2:
    name: TEST
    repos:
      - Red_Hat_Satellite_Tools_6_2_for_RHEL_6_Server_RPMs_x86_64
      - Red_Hat_Satellite_6_2_for_RHEL_7_Server_RPMs_x86_64
```

To export in this manner the '-e DEVELOPMENT' option must be used.
Exports to the 'environment' will be timestamped in the same way that DOV exports
are done, so ongoing incremental exports are possible.

### Help Output
```
usage: sat_export.py [-h] [-o ORG] [-e ENV] [-a | -i | -s SINCE] [-l] [-n]

Performs Export of Default Content View.

optional arguments:
  -h, --help            show this help message and exit
  -o ORG, --org ORG     Organization (Uses default if not specified)
  -e ENV, --env ENV     Environment config
  -a, --all             Export ALL content
  -i, --incr            Incremental Export of content since last run
  -s SINCE, --since SINCE
                        Export content since YYYY-MM-DD HH:MM:SS
  -l, --last            Display time of last export
  -n, --nogpg           Skip GPG checking
  -r, --repodata        Include repodata for repos with no incremental content

```

### Examples
```
./sat_export.py -e DEV              # Incr export of repos defined in the DEV config
./sat_export.py -o AnotherOrg       # Incr export of DoV for a different org
./sat_export.py -e DEV -a           # Full export of repos defined in the DEV config

Output file format will be:
sat_export_2016-07-29_DEV_00
sat_export_2016-07-29_DEV_01
sat_export_2016-07-20_DEV.sha256
```

# sat_import
This companion script to sat_export, running on the Disconnected Satellite
performs a sha256sum verification of each part of the specified archive prior
to extracting the transferred content to disk.

Once the content has been extracted, a sync is triggered of each repository
in the import set. Note that repositories MUST be enabled on the disconnected
satellite prior to the sync working - for this reason a `nosync` option (-n)
exists so that the repos can be extracted to disk and then enabled before the
sync occurs. In order to not overload the Satellite during the sync, the
repositories will be synced in smaller batches, the number of repos in a batch
being defined in the config.yml file. (It has been observed on systems with a
large number of repos that triggering a sync on all repos at once pretty much
kills the Satellite until the sync is complete)

All imports are treated as Incremental, and the source tree will be removed on 
successful import/sync.

The input archive files can also be automatically removed on successful import/sync
with the (-r) flag.

The last successfully completed import can be identified with the (-l) flag.

### Help Output
```
usage: sat_import.py [-h] [-o ORG] -d DATE [-n] [-r] [-l]

Performs Import of Default Content View.

optional arguments:
  -h, --help            show this help message and exit
  -o ORG, --org ORG     Organization (Uses default if not specified)
  -d DATE, --date DATE  Date/name of Import fileset to process (YYYY-MM-DD_NAME)
  -n, --nosync          Do not trigger a sync after extracting content
  -r, --remove          Remove input files after import has completed
  -l, --last            Show the last successfully completed import date
```

### Examples
```
./sat_import.py -d 2016-07-29_DEV -n            # Import content defined in DEV.yml but do not sync
./sat_import.py -d 2016-07-29_DoV               # Extract a DoV export but do not sync it
./sat_import.py -o MyOrg -l                     # Lists the date of the last successful import
./sat_import.py -o AnotherOrg -d 2016-07-29_DEV # Import content for a different org
```


# clean_content_views
This script removes orphaned versions of either all or nominated content views.
This should be run periodically to clean out old/unused content view data from
the mongo database and improve the responsiveness of the Satellite server.
Any orphaned versions older than the last in-use version are purged (orphans
between in-use versions will NOT be purged). There is a keep (-k) option that
allows a specific number of versions older than the last in-use to be kept as
well, allowing for possible rollback of versions.

Content views to clean can be defined by either:
  - Specific content views defined in the main config file 
  - All content views (-a)

The dry run (-d) option can be used to see what would be published for a
given command input.

The defaults are configured in the main config.yml file in a YAML block like this:
```
cleanup:
  content_views:
    - view: RHEL Server
      keep: 1
    - view: RHEL Workstation
      keep: 3
```
This configuration will clean only the two listed content views, and keep the 
specified number of versions beyond the oldest in-use.


```
usage: clean_content_views.py [-h] [-o ORG] [-a] [-d]

Cleans content views for specified organization.

optional arguments:
  -h, --help            show this help message and exit
  -o ORG, --org ORG     Organization (Uses default if not specified)
  -k KEEP, --keep KEEP  How many old versions to keep (only used with -a)
  -a, --all             Clean ALL content views
  -d, --dryrun          Dry Run - Only show what will be cleaned
```

### Examples
```
./clean_content_views.py		# Clean views using the default config
./clean_content_views.py -a -k 2	# Clean all views but keep the 2 oldest
./clean_content_views.py -a -d		# Show what would be done to clean all views 
```



# publish_content_views
Publishes new content to the Library environment. The following can be published:
  - Specific content views defined in the main config file
  - All content views (-a)

The dry run (-d) option can be used to see what would be published for a
given command input.

The defaults are configured in the main config.yml file in a YAML block like this:
```
publish:
  content_views:
    - RHEL Server
    - RHEL Workstation
```
This configuration will publish only the two listed content views.


```
usage: publish_content_view.py [-h] [-o ORG] [-a] [-d]

Publishes content views for specified organization.

optional arguments:
  -h, --help         show this help message and exit
  -o ORG, --org ORG  Organization (Uses default if not specified)
  -a, --all          Publish ALL content views
  -d, --dryrun       Dry Run - Only show what will be published
```

### Examples
```
./publish_content_view.py		    # Publish the default content views
./publish_content_view.py -a	 	    # Publish ALL content views
./publish_content_view.py -a -o OtherOrg -d # Dry-run on all OtherOrg views
```


# promote_content_views
Promotes content from the previous lifecycle environment stage.
If a lifecycle is defined as Library -> Test -> Quality -> Production, defining
the target environment (-e) as 'Quality' will promote matching content views
from Test -> Quality.

The following can be promoted:
  - Specific content views defined in the main config file
  - All content views (-a)

The dry run (-d) option can be used to see what would be promoted for a
given command input.

The defaults are configured in the main config.yml file in a YAML block like this:
```
promotion:
  lifecycle1:
    name: Quality
    content_views:
      - RHEL Server
      - RHEL Workstation

  lifecyclec2:
    name: Desktop QA
    content_views:
      - RHEL Workstation
```
If multiple lifecycle streams are used in your Satellite installation, the
use of the config.yml definition is strongly recommended to avoid views being
promoted into the wrong lifecycle stream. This is more likely to be an
issue promoting views from the Library, as this is shared by all environments.

```
usage: promote_content_view.py [-h] -e ENV [-o ORG] [-a] [-d]

Promotes content views for specified organization to the target environment.

optional arguments:
  -h, --help         show this help message and exit
  -e ENV, --env ENV  Target Environment (e.g. Development, Quality,
                     Production)
  -o ORG, --org ORG  Organization (Uses default if not specified)
  -a, --all          Promote ALL content views
  -d, --dryrun       Dry Run - Only show what will be promoted
```

### Examples
```
./promote_content_view.py -e Quality		# Promote default views to Quality
./promote_content_view.py -e Production -a      # Promote all views to Production
./promote_content_view.py -e Quality -d         # See what would be done for Quality
```

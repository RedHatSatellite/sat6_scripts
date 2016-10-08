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

logging:
  dir: /var/log/sat6-scripts     (Directory to use for logging)
  debug: [True|False]

export:
  dir: /var/sat-export           (Directory to export content to - Connected Satellite)

import:
  dir: /var/sat-content          (Directory to import content from - Disconnected Satellite)
  syncbatch: 10                  (Number of repositories to sync at once during import)
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

To export a selected repository set, a config file must exist in the config directory.
The name of the config file is the 'environment' that the configuration applies to.
This is useful if you have a development and production disconnected Satellite and
don't want to export the full DOV to the development environment. In this case
we will name the config file DEVELOPMENT.yml and its contents will look like the
example below. Repository names are the LABEL taken from the Satellite server and
must maintain the YAML array formatting.

```
env:
  name: DEVELOPMENT
  repos: [
           Red_Hat_Enterprise_Linux_7_Server_RPMs_x86_64_7Server,
           Red_Hat_Enterprise_Linux_7_Server_-_Extras_RPMs_x86_64,
           Red_Hat_Enterprise_Linux_7_Server_-_RH_Common_RPMs_x86_64_7Server,
         ]
```
To export in this manner the '-e DEVELOPMENT' option must be used.
Exports to the 'environment' will be timestamped in the same way that DOV exports
are done, so ongoing incremental exports are possible.

### Help Output
```
usage: sat_export.py [-h] -o ORG [-e ENV] [-a | -i | -s SINCE] [-l] [-n]

Performs Export of Default Content View.

optional arguments:
  -h, --help            show this help message and exit
  -o ORG, --org ORG     Organization
  -e ENV, --env ENV     Environment config file
  -a, --all             Export ALL content
  -i, --incr            Incremental Export of content since last run
  -s SINCE, --since SINCE
                        Export content since YYYY-MM-DD HH:MM:SS
  -l, --last            Display time of last export
  -n, --nogpg           Skip GPG checking

```

### Examples
```
./sat_export.py -o MyOrg -e DEV     # Incr export of repos defined in DEV.yml
./sat_export.py -o MyOrg            # Incr export of DoV
./sat_export.py -o MyOrg -e DEV -a  # Full export of repos defined in DEV.yml

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


### Help Output
```
usage: sat_import.py [-h] -o ORG -d DATE [-n] [-r]

Performs Import of Default Content View.

optional arguments:
  -h, --help            show this help message and exit
  -o ORG, --org ORG     Organization
  -d DATE, --date DATE  Date/name of Import fileset to process (YYYY-MM-DD_NAME)
  -n, --nosync          Do not trigger a sync after extracting content
  -r, --remove          Remove input files after import has completed
```

### Examples
```
./sat_import.py -o MyOrg -d 2016-07-29_DEV  # Import content defined in DEV.yml
./sat_import.py -o MyOrg -d 2016-07-29_DoV  # Import a DoV export
```

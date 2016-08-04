# sat6_scripts
Scripts to automate various Satellite 6 tasks.

These scripts have been written and tested using Satellite 6.2.0 on RHEL7


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
  --admin true
```


## Assumptions
For content import to a disconnected Satellite, it is assumed that the relevant
subscription manifest has been uploaded on the disconnected satellite. For the
_import with sync_ option (default), the repositories on the disconnected satellite
must have already been enabled and added to the import sync plan.


## Configuration
A YAML based configuration file is in config/config.yml.example  
The example file needs to be copied to config/config.yml and customised as
required:

```
satellite:
  url: https://sat6.example.org
  username: svc-api-user
  password: 1t$a$3cr3t

logging:
  dir: /var/log/sat6-scripts     (Directory to use for logging)
  debug: [True|False]
```

## Log files
Most scripts in this project will write output to satellite.log in the directory
specified in the config file.


## Scripts in this project

- **check_sync**
A quick method to check the status of sync tasks from the command line.
Will show any sync tasks that have stuck in a 'paused' state, as well as any
tasks that have stopped but been marked as Incomplete.
Running with the -l flag will loop the check until terminated with CTRL-C


- **clean_content_views**
This script removes orphaned versions of either all or nominated content views.
This should be run periodically to clean out old/unused content view data from
the mongo database and improve the responsiveness of the Satellite server.

Content views to clean can be defined by:
  - All content views (-a)
  - All content views defined in an input file (-i)
  - All content views EXCEPT those defined in an input file (-x)

The dry run (-d) option can be used to see what would be published for a
given command input.

If using an input file, the format is one content view name per line.

```
usage: clean_content_views.py [-h] -o ORG [-x FILE | -i FILE | -a] [-d]

Cleans content views for specified organization.

optional arguments:
  -h, --help            show this help message and exit
  -o ORG, --org ORG     Organization
  -x FILE, --exfile FILE
                        Cleans all content views EXCEPT those listed in file
  -i FILE, --infile FILE
                        Clean only content views listed in file
  -a, --all             Clean ALL content views
  -d, --dryrun          Dry Run - Only show what will be cleaned
```

- **publish_content_views**
Publishes new content to the Library environment. The following can be published:
  - All content views (-a)
  - All content views defined in an input file (-i)
  - All content views EXCEPT those defined in an input file (-x)

The dry run (-d) option can be used to see what would be published for a
given command input.

If using an input file, the format is one content view name per line.

```
usage: publish_content_view.py [-h] -o ORG [-x FILE | -i FILE | -a] [-d]

Publishes content views for specified organization.

optional arguments:
  -h, --help            show this help message and exit
  -o ORG, --org ORG     Organization
  -x FILE, --exfile FILE
                        Publish all content views EXCEPT those listed in file
  -i FILE, --infile FILE
                        Publish only content views listed in file
  -a, --all             Publish ALL content views
  -d, --dryrun          Dry Run - Only show what will be published
```

- **promote_content_views**
Promotes content from the previous lifecycle environment stage.
If a lifecycle is defined as Library -> Test -> Quality -> Production, defining
the target environment (-e) as 'Quality' will promote matching content views
from Test -> Quality.

The following can be promoted:
  - All content views (-a)
  - All content views defined in an input file (-i)
  - All content views EXCEPT those defined in an input file (-x)

The dry run (-d) option can be used to see what would be promoted for a
given command input.

If using an input file, the format is one content view name per line.

If multiple lifecycle streams are used in your Satellite installation, the
use of include/exclude files is strongly recommended to avoid views being
promoted into the wrong lifecycle stream. This is more likely to be an
issue promoting views from the Library, as this is shared by all environments.

```
usage: promote_content_view.py [-h] -e ENV -o ORG [-x FILE | -i FILE | -a] [-d]

Promotes content views for specified organization to the target environment.

optional arguments:
  -h, --help            show this help message and exit
  -e ENV, --env ENV     Target Environment (Development, Quality, Production)
  -o ORG, --org ORG     Organization
  -x FILE, --exfile FILE
                        Promote all content views EXCEPT those listed in file
  -i FILE, --infile FILE
                        Promote only content views listed in file
  -a, --all             Promote ALL content views
  -d, --dryrun          Dry Run - Only show what will be promoted
```

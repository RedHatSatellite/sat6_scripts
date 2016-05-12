# sat6_scripts
Scripts to automate various Satellite 6 tasks.

These scripts have been written and tested using Satellite 6.2 Beta on RHEL7

# Requirements
The Export and Import scripts are intended to be run on the Satellite server directly.
Other scripts may be run from the Satellite server or from a management host.

* You will need to install PyYAML to use these scripts.
yum -y install PyYAML

* The scripts make use of the Satellite REST API, and require an admin account on the Satellite server.
hammer user create --login svc-api --firstname API --lastname User --password='AP1Us3r' \
  --mail no-reply@example.org --auth-source-id 1 --organization-ids 1 --default-organization-id 1 \
  --timezone 'Canberra' --admin true

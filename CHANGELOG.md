# Changelog
All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Fixed
- Fix unreferenced var in check_disk_space function
- Various minor README corrections


## [1.2.1] - 2017-12-11
### Fixed
- Incorrect mapping of days in auto_content.py
- Support for username:token authentication to Artifactory Puppet Forge server
- Email now supports multiple recipients


## [1.2.0] - 2017-12-10
### Added
- push_puppetforge now supports jFrog Artifiactory repository via HTTP POST
- sat_import now checks for exports that have not been imported (missed/skipped)
- sat_import --fixhistory option to force align import/export histories
- Email notification capability for use when automating content scripts
- Add unattended option to allow scripts to be automated
- auto_content scripts to allow unattended import/publish/promote/clean activity

### Changed
- --notar export saved in /cdn_export dir rather than /export to prevent it being deleted

### Removed
- Skip GPG short option (-n)


## [1.1.1] - 2017-10-25
### Added
- Allow limiting of Publish and Promotion to specified number of CV's at once.


## [1.1.0] - 2017-10-23
### Added
- Proxy support for download_manifest
- Quiet option in publish/promote scripts
- Full repo package comparison written to log during disconnected import
- Provide a history of successful content exports and imports
- Present a warning if import has already been performed for given dataset
- Option to leave export in unarchived format (--notar)
- Option to force a disconnected (import only) Satellite to export if required

### Changed
- Updated exit codes throughout the scripts
- Updated export dataset name format to allow for multiple exports per day
- Updated to Semantic Versioning

### Fixed
- Various minor bugfixes and typos
- Fixed bug in DoV export

### Deprecated
- Skip GPG short option (-n) will be removed in 1.2.0. Long option (--nogpg) will remain.


## [1.0] - 2017-03-06
- Initial 'public' release

## 0.6 - 2017-02-27
- Last of a series of pre-release betas

[Unreleased]: https://github.com/ggatward/sat6_scripts/compare/1.2.1...HEAD
[1.2.1]: https://github.com/ggatward/sat6_scripts/compare/1.2.0...1.2.1
[1.2.0]: https://github.com/ggatward/sat6_scripts/compare/1.1.1...1.2.0
[1.1.1]: https://github.com/ggatward/sat6_scripts/compare/1.1.0...1.1.1
[1.1.0]: https://github.com/ggatward/sat6_scripts/compare/1.0...1.1.0
[1.0]: https://github.com/ggatward/sat6_scripts/compare/0.6...1.0

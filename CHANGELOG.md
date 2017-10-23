# Changelog
All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/ggatward/sat6_scripts/compare/1.1.0...HEAD
[1.1.0]: https://github.com/ggatward/sat6_scripts/compare/1.0...1.1.0
[1.0]: https://github.com/ggatward/sat6_scripts/compare/0.6...1.0

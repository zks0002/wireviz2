[//]: # (Types of changes)
[//]: # ("Added" for new features)
[//]: # ("Changed" for changes in existing functionality)
[//]: # ("Deprecated" for soon-to-be removed features)
[//]: # ("Removed" for now removed features)
[//]: # ("Fixed" for any bug fixes)
[//]: # ("Security" in case of vulnerabilities)

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to 
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.3.0 - 2021-07-01

### Added 

* RF cables

## 1.2.0 - 2021-06-22

### Changed

* HTML page title now reflects the outfile basename
* Header on the HTML page now reflects the outfile basename

### Fixed

* `show_equiv: true` will not throw an exception if no wire gauge is given

## 1.1.0 - 2021-06-22

### Added

* Common library file now included in distribution
* `-c`/`--common`/`--prepend-common-lib` option includes the common library.
* `click` is now an installation dependency.

### Changed

* Implemented command line interface with `click` instead of `argparse`

## 1.0.1 - 2021-06-21

### Fixed

* Entry point for console script corrected sire the wireviz executable worked

## 1.0.0 - 2021-06-21

### Added

* Length units of inches now supported.

## 0.2

Initial RRC release. See [GitHub's
Changelog](https://github.com/formatc1702/WireViz/blob/master/docs/CHANGELOG.md)
for previous changes.

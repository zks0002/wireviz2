# WireViz

## Summary

WireViz is a tool for easily documenting cables, wiring harnesses and connector
pinouts. It takes plain text, YAML-formatted files as input and produces
beautiful graphical output (SVG, PNG, ...) thanks to 
[GraphViz](https://www.graphviz.org/). It handles automatic BOM (Bill of
Materials) creation and has a lot of extra features.

RRC's GitLab hosted wireviz was cloned from the [formatc1702/WireViz repo on 
GitHub](https://github.com/formatc1702/WireViz/tree/v0.2), v0.2. Updates since 
this snapshot are maintained by RRC and uses the versioning API below. The
original WireViz was released under the [GPL-3.0 license](LICENSE); copyright
and license notices are therefore preserved.

Installation and usage instructions are located on the
[ISBU HW Wiki](http://isbuhome/isbuwiki/index.php/Wireviz).

## Development notes

### Requirements

WireViz requires Python 3.7 or later.

WireWiz requires GraphViz to be installed in order to work. See the [GraphViz
download page](https://graphviz.org/download/) for OS-specific instructions.

_Note_: Ubuntu 18.04 LTS users in particular may need to separately install
Python 3.7 or above, as that comes with Python 3.6 as the included system
Python install.

### Build a Distribution

From the repository root directory, run the following:

`py setup.py dist`

This will use a temporary build/ directory to build the files, and the
distribution files are located in dist/.

Once the distribution is built, you can deploy.

### Deployment

The following command uploads the distribution files to GitLab's newpcb PyPi
package registry:

`py -m twine upload -r rrc-gitlab-wireviz dist/* --cert "C:\Users\%USERNAME%\ca-bundle.crt"`

This assumes that the following content is in `C:\\Users\\%username%\\.pypirc`:

```
[rrc-gitlab-wireviz]
repository = https://gitlab.rinconres.com/api/v4/projects/2343/packages/pypi
username = __token__
password = <your personal access token>
```

### Versioning API

The only direct compatibility between
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) (SemVer) and
[PEP 440](https://www.python.org/dev/peps/pep-0440/) (Python's recommended
approach to identifying versions, supported by PyPI) is a MAJOR.MINOR.PATCH
scheme. However, through trial and error, the SemVer pre-release syntax
`X.Y.Z-aN` is accepted by PyPI (indeed, PEP 440
[Appendix B](https://www.python.org/dev/peps/pep-0440/#appendix-b-parsing-version-strings-with-regular-expressions)
includes a regex as defined by the [packaging](https://github.com/pypa/packaging/tree/master/packaging)
project that supports this format). That is, the PEP 440-compatible `X.Y.ZaN`
syntax can be converted to the SemVer-compatible `X.Y.Z-aN` syntax (note the
extra dash) without penalty, and PyPI will still recognize the version. To that
end, the following versioning identification is used:

**MAJOR**.**MINOR**.**PATCH**\[**-**{**a**|**b**|**rc**}**N**\]\[**+META**\]

* **MAJOR**, **MINOR**, and **PATCH** comply with
  [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html#semantic-versioning-specification-semver)
  and are required for *every* release.
* Pre-releases are optional. If included, it is specified immediately after
  the PATCH version. A pre-release is prefixed with a `-`, identified as
  one of the following types, and suffixed with a non-negative version number
  **N**:
    * *alpha* (**a**), indicating content unverified through test. There is no
      commitment that this will escalate to a beta release, release candidate,
      or final release.
    * *beta* (**b**), indicating that code is complete and testing is underway.
    * *release candidate* (**rc**), indicating that code and testing is complete
      and final preparations are being made for release.
* Meta data or build data (**META**) is optional. If included, it is specified
  immediately after the pre-release identifier (if present) or the PATCH version
  (if no pre-release is specified). Meta data is prefixed with a `+` and
  complies with both
  [PEP 440](https://www.python.org/dev/peps/pep-0440/#local-version-identifiers)
  and [SymVer 2.0.0](https://semver.org/spec/v2.0.0.html#spec-item-10).

Post- and development-releases are not supported. Instead, increment the
appropriate MAJOR, MINOR, or PATCH version with an alpha release.


#!/usr/bin/env python3
import setuptools
import pathlib
import re
from typing import List

ROOT = pathlib.Path(__file__).parent
REPO = ROOT / "wireviz"


def get_version() -> str:
    """Retrieve the version from wireviz/__init__.py.
    The version is stored in one place in this repository, and since the
    version can't be retrieved by the wireviz module during installation
    (e.g., pip install rrc-wireviz), it will hold the master copy.
    """
    # https://www.python.org/dev/peps/pep-0440/#version-scheme
    # https://regex101.com/r/Ly7O1x/319
    # See readme.md for the Versioning Public API
    regex = (r"""__version__\s*=\s*['"]{1,3}"""
             r"(?P<release>(?:0|[1-9])\d*(?:\.(?:0|[1-9]\d*)){2})"
             r"(?:-(?P<pre>(?P<prel>a|b|rc)(?P<pren>(?:0|[1-9])\d*)))?"
             r"(?:\+(?P<local>[a-z\d]+(?:[-_\.][a-z\d]+)*))?"
             r"""['"]{1,3}""")

    with open(REPO / '__init__.py') as f:
        vsrc = re.search(regex, f.read())

    if not vsrc:
        raise ValueError(f"Invalid __version__ in '{f.name}'.")

    version = vsrc.group('release')
    if vsrc.group('pre'):
        version += f"-{vsrc.group('pre')}"
    if vsrc.group('local'):
        version += f"+{vsrc.group('local')}"
    return version


def get_dependencies(filename: str) -> List[str]:
    """Get a list of dependencies fit for the install_requires option."""
    with open(ROOT / filename, 'r') as f:
        ret = [re.sub(r"\s", "", req) for req in f.readlines()
               # Remove blank lines, comments, and options beginning with a dash
               if req.strip() and not (req.startswith('#') or
                                       req.startswith('-'))]
    return ret


if __name__ == "__main__":
    setuptools.setup(
        name="rrc-wireviz",
        version=get_version(),
        url="https://gitlab.rinconres.com/isbu/hardware/scripts/wireviz",
        download_url="https://gitlab.rinconres.com/isbu/hardware/scripts/wireviz",  # noqa
        project_urls={
            "Bug Tracker": "https://gitlab.rinconres.com/isbu/hardware/scripts/wireviz/-/issues",  # noqa
            "Documentation": "https://gitlab.rinconres.com/isbu/hardware/scripts/wireviz/-/blob/master/readme.md",  # noqa
            "Source Code": "https://gitlab.rinconres.com/isbu/hardware/scripts/wireviz",  # noqa
        },
        author="Daniel Rojas",
        maintainer="Zack Sheffield",
        maintainer_email="zks@rincon.com",
        classifiers=[
            "Development Status :: 4 - Beta",
            "Environment :: Console",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Topic :: Utilities",
            "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        ],
        license="GPLv3",
        description="Easily document cables and wiring harnesses",
        long_description=open(ROOT / "readme.md").read(),
        long_description_content_type="text/markdown",
        keywords=('cable connector hardware harness wiring '
                  'wiring-diagram wiring-harness'),
        install_requires=get_dependencies("install_requires.txt"),
        packages=["wireviz"],
        entry_points={
            "console_scripts": ["wireviz=wireviz.wireviz:main"],
        },
        python_requires=">=3.7",
        setup_requires=get_dependencies("setup_requires.txt"),
    )

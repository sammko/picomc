import sys

# This is referenced in setup.py
from picomc.main import main

from ._version import __version__

del _version

MINPYVERSION = (3, 7, 0)


if sys.version_info < MINPYVERSION:
    print("picomc, version {}".format(__version__))
    print(
        "picomc requires at least Python version "
        "{}.{}.{}. You are using {}.{}.{}.".format(*MINPYVERSION, *sys.version_info)
    )
    sys.exit(1)

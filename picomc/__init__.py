import sys

from picomc._version import __version__
from picomc.cli import picomc_cli

MINPYVERSION = (3, 7, 0)

if sys.version_info < MINPYVERSION:
    print("picomc, version {}".format(__version__))
    print(
        "picomc requires at least Python version "
        "{}.{}.{}. You are using {}.{}.{}.".format(*MINPYVERSION, *sys.version_info)
    )
    sys.exit(1)


def main():
    picomc_cli()

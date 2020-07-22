from contextlib import ExitStack

from picomc.cli import picomc_cli


def main():
    with ExitStack() as es:
        picomc_cli(obj=es)

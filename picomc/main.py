from contextlib import ExitStack

from picomc.cli import picomc_cli
from picomc.env import Env


def main():
    with ExitStack() as estack:
        Env.estack = estack
        picomc_cli()

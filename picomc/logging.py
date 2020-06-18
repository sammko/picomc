import logging

import coloredlogs

logger = logging.getLogger("picomc.cli")


def initialize(debug):
    coloredlogs.install(
        level="DEBUG" if debug else "INFO",
        fmt="%(levelname)s %(message)s",
        logger=logger,
    )

import logging

import coloredlogs

logger = logging.getLogger("picomc.cli")
debug = False


def initialize(debug_):
    global debug
    debug = debug_
    coloredlogs.install(
        level="DEBUG" if debug else "INFO",
        fmt="%(levelname)s %(message)s",
        logger=logger,
    )

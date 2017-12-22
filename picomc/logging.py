import logging

logger = logging.getLogger('picomc.cli')


def initialize(debug):
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)-4s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.debug("Logging succesfully initialized.")

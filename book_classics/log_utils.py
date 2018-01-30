import logging

import coloredlogs


def setup_logging(verbose: bool = True) -> None:
    if verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level,
                        format="[%(name)s %(levelname)s] %(message)s")
    coloredlogs.install(level=log_level)
    for module in ["requests"]:
        logging.getLogger(module).setLevel(logging.WARNING)

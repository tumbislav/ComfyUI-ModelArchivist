# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: __main__.py
# purpose: Entry point
# ---------------------------------------------------------------------------

import argparse
import logging.config
import sys
from backend.config import load_config
from backend.repository.repository import start_repo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='full path of config file', default=None)
    args = parser.parse_args(argv)

    logging_initialized = False
    try:
        config = load_config(args.config)
        logging.config.dictConfig(config.log_config)
        logging_initialized = True
        logger = logging.getLogger('archivist.root')
        logger.debug('Logging initialized')
        start_repo()
        logger.info('Back end initialized')
    except Exception as error:
        message = f'Backend initialization failed: {error}'
        if logging_initialized:
            logging.getLogger('archivist.root').exception(message)
        print(message, file=sys.stderr)
        return 1

    from .server.gui import start_ui
    start_ui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

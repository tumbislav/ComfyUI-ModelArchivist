# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: __main__.py
# purpose: Entry point
# ---------------------------------------------------------------------------

import argparse
import logging.config
from backend.config import load_config
from backend.model.archivist import start_archivist

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='full path of config file', default=None)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        logging.config.dictConfig(config.log_config)
        logger = logging.getLogger('archivist.root')
        logger.debug('Logging initialized')
        start_archivist()
        logger.info('Back end initialized')
    except Exception as e:  # noqa
        raise e
    from .server.gui import start_ui
    start_ui()

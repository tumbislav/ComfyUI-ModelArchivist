# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: __main__.py
# purpose: Entry point
# ---------------------------------------------------------------------------

import argparse
import logging
from backend.config import load_config
from backend.model.archivist import start_archivist

logger = logging.getLogger('model_archivist')
logging.basicConfig(filename='model_archivist.log', level=logging.INFO)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='full path of config file', default=None)
    args = parser.parse_args()
    try:
        load_config(args.config)
        start_archivist()
    except Exception as e:  # noqa
        logger.critical(f'Could not initialize service, aborting.')
        raise e
    from .server.gui import start_ui
    start_ui()

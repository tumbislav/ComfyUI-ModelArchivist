# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: __main__.py
# purpose: Entry point
# ---------------------------------------------------------------------------

import argparse
import logging
from pathlib import Path
from .config.config import config
from .db.repository import repo
from .model.archivist import archivist
#from .server.gui import start_server

logger = logging.getLogger('model_archivist')
logging.basicConfig(filename='model_archivist.log', level=logging.INFO)


def main() -> None:
    """
    Get the configuration file, construct all the components of the application
    in the correct order and start the GUI in the default browser.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='full path of config file')
    args = parser.parse_args()
    try:
        config.attach(args.config, Path(__file__).resolve())
        repo.attach(config.db_path)
        archivist.attach(config, repo)
    except Exception as e:  # noqa
        logger.critical(f'Could not initialize the back end, Aborting.')
        raise e
    from .server.gui import start_server

    start_server()

if __name__ == "__main__":
    main()
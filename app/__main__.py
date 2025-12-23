# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: __main__.py
# purpose: Entry point
# ---------------------------------------------------------------------------

import argparse
import logging
from pathlib import Path
from app.config.config import config
from app.db.repository import repo
from app.model.archivist import archivist


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
        config.attach(Path(args.config))
        repo.attach(config.db_path)
        archivist.attach(config, repo)
    except Exception as e:  # noqa
        logger.critical(f'Unhandled exception: {e}. Aborting.')
        return

#    gui_start(service)


if __name__ == "__main__":
    main()
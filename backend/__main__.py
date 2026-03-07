# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: __main__.py
# purpose: Entry point
# ---------------------------------------------------------------------------

import argparse
import logging
from backend.config import load_config
from .db.repository import repo
from .model.archivist import archivist

logger = logging.getLogger('model_archivist')
logging.basicConfig(filename='model_archivist.log', level=logging.INFO)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='full path of config file', default=None)
    parser.add_argument('--user', help='user folder', default=None)
    args = parser.parse_args()
    try:
        cfg = load_config(args.config, args.user)
        first_run = repo.attach(cfg.db_path)
        archivist.attach(cfg, repo)
#        archivist.scan()
    except Exception as e:  # noqa
        logger.critical(f'Could not initialize the back end, aborting.')
        raise e

    # late import because gui requires archivist to be fully initialized
#    from .server.gui import start_server
#    start_server()

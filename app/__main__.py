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
        config.attach(args.config)
        repo.attach(config.db_path, True)
        archivist.attach(config, repo)
    except Exception as e:  # noqa
        logger.critical(f'Unhandled exception: {e}. Aborting.')
        raise e
    return
    models = archivist.get_models()
    for model in models:
        print()
        print(f'id={model.id}')
        print(f'sha256={model.sha256}')
        print(f'name={model.name}')
        print(f'type={model.type}')
        print(f'active_root={model.active_root}')
        print(f'inactive_root={model.inactive_root}')
        print(f'archive_root={model.archive_root}')
        print(f'is_active={model.is_active}')
        print(f'is_inactive={model.is_inactive}')
        print(f'is_archived={model.is_archived}')
        print(f'last_scan_id={model.last_scan_id}')
        print(f'scan_errors={model.scan_errors}')
        print(f'tags={",".join(_.tag for _ in model.tags)}')
        for component in model.components:
            print(f'   id={component.id}')
            print(f'   location={component.location}')
            print(f'   relative_path={component.relative_path}')
            print(f'   filename={component.filename}')
            print(f'   type={component.component_type}')
            print(f'   is_present={component.is_present}')
            print()
        print()

#    gui_start(service)


if __name__ == "__main__":
    main()
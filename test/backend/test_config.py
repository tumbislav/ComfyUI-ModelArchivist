from backend.config import load_config, get_config
from pathlib import Path


class TestConfig:
    def test_round_trip_config(self, tmp_path: Path):
        """
        Check that we can load and save the config file and get the same content
        """
        config_file = tmp_path /  'config_test.toml'
        config = load_config(config_file)

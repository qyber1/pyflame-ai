import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pyflame_ai.config import Config
from pyflame_ai.exceptions import ConfigNotFound


class TestConfig(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp_dir.name)

        patcher = patch("pyflame_ai.config.Path")
        self.addCleanup(patcher.stop)
        self.mock_path = patcher.start()

        self.mock_path.return_value.expanduser.return_value = self.config_path
        self.mock_path.return_value.__truediv__.side_effect = (
            lambda x: self.config_path / x
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_config_file_path(self):
        config = Config()
        self.assertEqual(config.file.name, "config.ini")

    def test_set_and_get_github_token(self):
        config = Config()
        config.set_github_token("test-token")

        token = config.get_github_token()
        self.assertEqual(token, "test-token")

    def test_update_github_token(self):
        config = Config()
        config.set_github_token("old-token")
        config.update_github_token("new-token")

        token = config.get_github_token()
        self.assertEqual(token, "new-token")

    def test_get_token_without_config_raises(self):
        config = Config()
        with self.assertRaises(ConfigNotFound):
            config.get_github_token()

    def test_config_exist_returns_false_when_empty(self):
        config = Config()
        result = config.config_exist()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
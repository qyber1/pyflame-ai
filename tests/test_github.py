import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from pyflame_ai.github import GitHubRefactor


class TestGitHubRefactor(unittest.TestCase):

    def setUp(self):
        self.source_code = "def foo():\n    return 1\n"
        self.new_code = "def foo():\n    return 2\n"
        self.file_path = Path("fake_path.py")

    @patch.object(Path, "read_text")
    @patch.object(Path, "write_text")
    @patch("pyflame_ai.github.Repo")  # Мокаем git
    @patch("pyflame_ai._styled._echo_error", side_effect=lambda msg: msg)
    def test_refactor_success(self, mock_error, mock_repo, mock_write, mock_read):
        mock_read.return_value = self.source_code

        mock_instance = MagicMock()
        mock_repo.return_value = mock_instance
        mock_instance.is_dirty.return_value = False
        mock_instance.remote.return_value.url = "https://github.com/test/repo.git"
        mock_instance.index.commit.return_value.hexsha = "123456"

        refactor = GitHubRefactor(str(self.file_path), "foo", self.new_code)
        result = refactor.refactor(token="TOKEN")

        self.assertIn("https://github.com/test/repo/commit/123456", result)

    def test_function_not_found(self):
        refactor = GitHubRefactor("dummy_path.py", "missing_func", "def new(): pass")

        with patch("pathlib.Path.read_text", return_value="def other(): pass"), \
                patch("pyflame_ai.github._echo_error") as mock_echo:
            mock_echo.side_effect = lambda msg: msg  # _echo_error возвращает текст
            result = refactor.refactor(token="fake_token")

        self.assertIsNotNone(result)
        self.assertEqual("Функция 'missing_func' не найдена ни на одном уровне", result)
        mock_echo.assert_called_once()


if __name__ == "__main__":
    unittest.main()

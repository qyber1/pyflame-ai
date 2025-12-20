import unittest
from unittest.mock import patch, MagicMock

from pyflame_ai.command import RefactorCommand, ConfigCommand, OpenReportCommand, SimpleRunCommand


class TestCommandRun(unittest.TestCase):

    @patch("pyflame_ai.command.subprocess.run")
    @patch("pyflame_ai.command.Parser")
    @patch("pyflame_ai.command.Client")
    @patch("pyflame_ai.command.click.confirm")
    @patch("pyflame_ai.command._echo_success")
    @patch("pyflame_ai.command._echo_warning")
    @patch("pyflame_ai.command._echo_usual")
    def test_run_success_without_github(
        self,
        mock_echo_usual,
        mock_echo_warning,
        mock_echo_success,
        mock_confirm,
        mock_client_cls,
        mock_parser_cls,
        mock_subprocess_run,
    ):

        mock_subprocess_run.return_value = MagicMock(
            returncode=0,
            stderr="",
        )

        mock_parser = MagicMock()
        mock_parser.parse.return_value = {
            "source_code": "def foo(): return 1",
            "function_totals": [
                {"function": "foo"}
            ]
        }
        mock_parser_cls.return_value = mock_parser

        mock_client = MagicMock()
        mock_client.get_refactor_code.return_value = "def foo(): return 2"
        mock_client_cls.return_value = mock_client

        mock_confirm.return_value = False

        cmd = RefactorCommand(
            path="test.py",
            output_filename="out.txt",
            samples=100,
            api_key="fake-key",
        )

        cmd.run()

        mock_subprocess_run.assert_called_once()
        mock_parser.parse.assert_called_once()
        mock_client.get_refactor_code.assert_called_once()

        mock_echo_usual.assert_any_call("Исходный код:")
        mock_echo_warning.assert_called_once()
        mock_echo_success.assert_any_call("def foo(): return 2")

class TestSimpleRunCommand(unittest.TestCase):

    @patch("pyflame_ai.command.subprocess.run")
    @patch("pyflame_ai.command.Parser")
    @patch("pyflame_ai.command._echo_success")
    def test_run_success(
        self,
        mock_echo_success,
        mock_parser_cls,
        mock_subprocess_run,
    ):
        mock_subprocess_run.return_value = MagicMock(
            returncode=0,
            stderr="",
        )

        mock_parser = MagicMock()
        mock_parser.parse.return_value = {"data": "parsed"}
        mock_parser_cls.return_value = mock_parser

        cmd = SimpleRunCommand(
            path="test.py",
            output_filename="out.txt",
            samples=100,
        )

        cmd.run()

        mock_subprocess_run.assert_called_once()
        mock_parser.parse.assert_called_once()
        mock_echo_success.assert_any_call("Сбор данных прошел успешно")
        mock_echo_success.assert_any_call("Парсинг данных PySpy прошел успешно")

    @patch("pyflame_ai.command.subprocess.run")
    @patch("pyflame_ai.command._echo_error")
    def test_run_file_not_found(
        self,
        mock_echo_error,
        mock_subprocess_run,
    ):
        mock_subprocess_run.return_value = MagicMock(
            returncode=1,
            stderr="No such file or directory",
        )

        cmd = SimpleRunCommand(
            path="missing.py",
            output_filename="out.txt",
            samples=100,
        )

        cmd.run()

        mock_echo_error.assert_called_once_with("Файл не найден")


class TestOpenReportCommand(unittest.TestCase):

    @patch("pyflame_ai.command.Parser")
    @patch("pyflame_ai.command.ReportRenderer")
    def test_open_report_success(
        self,
        mock_renderer_cls,
        mock_parser_cls,
    ):
        mock_parser = MagicMock()
        mock_parser.parse.return_value = {"report": "data"}
        mock_parser_cls.return_value = mock_parser

        mock_renderer = MagicMock()
        mock_renderer_cls.return_value = mock_renderer

        cmd = OpenReportCommand(
            filename="report.txt",
            raw=False,
        )

        cmd.run()

        mock_parser.parse.assert_called_once()
        mock_renderer.render.assert_called_once_with(
            {"report": "data"},
            False,
        )

    @patch("pyflame_ai.command.Parser")
    @patch("pyflame_ai.command._echo_error")
    def test_open_report_file_not_found(
        self,
        mock_echo_error,
        mock_parser_cls,
    ):
        mock_parser = MagicMock()
        mock_parser.parse.side_effect = FileNotFoundError("missing.txt")
        mock_parser_cls.return_value = mock_parser

        cmd = OpenReportCommand(
            filename="missing.txt",
            raw=False,
        )

        cmd.run()

        mock_echo_error.assert_called_once()


class TestConfigCommand(unittest.TestCase):

    @patch("pyflame_ai.command.Config")
    @patch("pyflame_ai.command.click.confirm")
    @patch("pyflame_ai.command.click.prompt")
    @patch("pyflame_ai.command._echo_success")
    def test_config_update_existing(
        self,
        mock_echo_success,
        mock_prompt,
        mock_confirm,
        mock_config_cls,
    ):
        mock_config = MagicMock()
        mock_config.config_exist.return_value = True
        mock_config_cls.return_value = mock_config

        mock_confirm.return_value = True
        mock_prompt.return_value = "new-token"

        cmd = ConfigCommand()
        cmd.run()

        mock_config.update_github_token.assert_called_once_with("new-token")
        mock_echo_success.assert_called_once_with("Токен успешно сохранен")

    @patch("pyflame_ai.command.Config")
    @patch("pyflame_ai.command.click.prompt")
    @patch("pyflame_ai.command._echo_success")
    def test_config_create_new(
        self,
        mock_echo_success,
        mock_prompt,
        mock_config_cls,
    ):
        mock_config = MagicMock()
        mock_config.config_exist.return_value = False
        mock_config_cls.return_value = mock_config

        mock_prompt.return_value = "token"

        cmd = ConfigCommand()
        cmd.run()

        mock_config.set_github_token.assert_called_once_with("token")
        mock_echo_success.assert_called_once_with("Токен успешно сохранен")


if __name__ == "__main__":
    unittest.main()
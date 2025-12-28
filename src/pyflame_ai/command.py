import subprocess
import sys

from ._styled import _echo_error, _echo_success
from .config import Config
from .exceptions import ConfigNotFound
from .github import GitHubRefactor
from .model import Client
from .parser import Parser


class Command:

    def __init__(self, path: str, output_filename: str, samples: int, api_key: str, dry_run: bool = False):
        """
        :param path: путь к исходному Python-файлу для анализа
        :param output_filename: имя файла для вывода данных py-spy
        :param samples: количество сэмплов для профилирования
        :param api_key: API ключ для обращения к модели DeepSeek
        :param dry_run: если True, код не будет пушиться в GitHub, только выводится готовый результат
        """
        self.path = path
        self.output_filename = output_filename
        self.samples = samples
        self.dry_run = dry_run
        self.client = Client(api_key=api_key)
        self.config = Config()

    def run(self):
        """
        Основная точка входа в программу.

        Последовательность действий:
        1. Запуск py-spy для сбора профиля выполнения.
        2. Обработка результатов py-spy через Parser.
        3. Запрос на рефакторинг функции через DeepSeek API.
        4. Если dry_run=True — вывод готового кода без пуша.
        5. Если dry_run=False — замена функции в исходном файле и пуш изменений в GitHub.

        :return: Сообщение о статусе выполнения или готовый код функции при dry_run
        """
        command = self._run_py_spy()

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True
            )
        except ConfigNotFound:
            return _echo_error('ОШИБКА: Файл конфигурации не существует, необходимо запустить: pyflame-ai config init')

        if result.returncode == 0:
            _echo_success('Сбор данных прошел успешно')
        else:
            if 'No such file or directory' in result.stderr:
                return _echo_error('Файл не найден')
            else:
                _echo_error('Произошла непредвиденная ошибка')
                return _echo_error(result.stderr)

        _parser = Parser(self.output_filename)
        result = _parser.parse()
        refactor_code = self.client.get_refactor_code(result['source_code'])
        if self.dry_run:
            return _echo_success('Готовый код к рефакторингу\n' + refactor_code)

        github_refactor = GitHubRefactor(self.path, result['function_totals'][0]['function'], refactor_code)
        url_commit = github_refactor.refactor()
        return _echo_success('Успешно создан коммит: ' + url_commit)

    def _run_py_spy(self):
        win_available = '-s' if sys.platform == 'win32' else ''
        return 'py-spy record {0} -o {1} --format raw -r {2} -- python {3}'.format(
            win_available,
            self.output_filename,
            self.samples,
            self.path
        )

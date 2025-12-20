import subprocess
import sys

import click

from ._styled import _echo_error, _echo_success, _echo_warning, _echo_usual
from .config import Config
from .exceptions import ConfigNotFound
from .github import GitHubRefactor
from .model import Client
from .parser import Parser, ReportRenderer


class SimpleRunCommand:
    """
    Команда для упрощённого анализа производительности Python-программы.

    Используется для запуска профилирования с помощью py-spy,
    последующего анализа полученных данных и вывода отчёта
    без выполнения автоматического рефакторинга кода.
    """

    def __init__(self, path: str, output_filename: str, samples: int):
        """
        Инициализация команды простого анализа.

        :param path: путь к исходному Python-файлу для анализа
        :param output_filename: имя файла для сохранения результатов py-spy
        :param samples: количество сэмплов профилирования
        """
        self.path = path
        self.output_filename = output_filename
        self.samples = samples
        self.config = Config()
        self.renderer = ReportRenderer()
        self.result = None

    def run(self) -> None:
        """
        Запускает профилирование и анализ производительности без рефакторинга.

        Последовательность выполнения:
        1. Запуск py-spy для сбора профиля выполнения программы.
        2. Парсинг профилировочных данных.
        3. Подготовка структурированного отчёта.
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
            _echo_error(
                'ОШИБКА: Файл конфигурации не существует, необходимо запустить: pyflame-ai config init'
            )
            return

        if result.returncode == 0:
            _echo_success('Сбор данных прошел успешно')
        else:
            if 'No such file or directory' in result.stderr:
                _echo_error('Файл не найден')
            else:
                _echo_error('Произошла непредвиденная ошибка')
                _echo_error(result.stderr)
            return

        parser = Parser(self.output_filename)
        self.result = parser.parse()
        _echo_success('Парсинг данных PySpy прошел успешно')

    def _run_py_spy(self) -> str:
        """
        Формирует команду запуска py-spy с учётом операционной системы.

        :return: строка команды для выполнения py-spy
        """
        win_available = '-s' if sys.platform == 'win32' else ''
        return (
            'py-spy record {0} -o {1} --format raw -r {2} -- python {3}'
            .format(win_available, self.output_filename, self.samples, self.path)
        )

    def report_renderer(self) -> None:
        """
        Выводит отформатированный отчёт о производительности в консоль.
        """
        _echo_success('Ниже представлен отчет:')
        self.renderer.render(self.result)


class RefactorCommand(SimpleRunCommand):
    """
    Команда для полного цикла анализа и интеллектуального рефакторинга кода.

    Расширяет SimpleRunCommand, добавляя этап генерации рекомендаций
    по оптимизации кода с использованием языковой модели DeepSeek
    и возможность применения изменений через Git.
    """

    def __init__(self, path: str, output_filename: str, samples: int, api_key: str):
        """
        Инициализация команды рефакторинга.

        :param path: путь к анализируемому Python-файлу
        :param output_filename: имя файла отчёта py-spy
        :param samples: количество сэмплов профилирования
        :param api_key: API-ключ для доступа к языковой модели DeepSeek
        """
        self.client = Client(api_key=api_key)
        super().__init__(path, output_filename, samples)

    def run(self) -> None:
        """
        Запускает полный сценарий анализа и рефакторинга.

        Этапы выполнения:
        1. Профилирование и анализ производительности (SimpleRunCommand).
        2. Генерация оптимизированного кода через языковую модель.
        3. Выбор пользователем способа применения результата:
           - вывод в консоль;
           - автоматический коммит в Git-репозиторий.
        """
        super().run()

        refactor_code = self.client.get_refactor_code(
            self.result['source_code']
        )

        use_github = click.confirm(
            'Выполнить рефакторинг кода? (y — выполнить, n — вывести в консоль)'
        )

        if use_github:
            github_refactor = GitHubRefactor(
                self.path,
                self.result['function_totals'][0]['function'],
                refactor_code
            )
            try:
                url_commit = github_refactor.refactor(
                    self.config.get_github_token()
                )
                if url_commit:
                    _echo_success('Успешно создан коммит: ' + url_commit)
            except ConfigNotFound:
                _echo_error(
                    'Файл конфигурации не создан. Выполните команду:\npyflame-ai config'
                )
        else:
            _echo_usual('Исходный код:')
            _echo_warning(self.result['source_code'] + '\n')
            _echo_usual('Готовый код для рефакторинга:')
            _echo_success(refactor_code)


class OpenReportCommand:
    """
    Команда для просмотра ранее сохранённого отчёта профилирования.
    """

    def __init__(self, filename: str, raw: bool) -> None:
        """
        :param filename: путь к файлу с результатами py-spy
        :param raw: флаг вывода отчёта в необработанном виде
        """
        self.filename = filename
        self.raw = raw
        self.parser = Parser(filename)
        self.renderer = ReportRenderer()

    def run(self) -> None:
        """
        Загружает и отображает отчёт о производительности.
        """
        try:
            result = self.parser.parse()
        except FileNotFoundError as e:
            _echo_error(f'Файла не существует: {e.filename}')
            return

        self.renderer.render(result, self.raw)


class ConfigCommand:
    """
    Команда для инициализации и обновления конфигурации приложения.
    """

    def __init__(self) -> None:
        """
        Создаёт объект конфигурации приложения.
        """
        self.config = Config()

    def run(self) -> None:
        """
        Создаёт или обновляет файл конфигурации с учётными данными GitHub.
        """
        if self.config.config_exist():
            confirm = click.confirm(
                click.style(
                    'Файл конфигурации с GitHub токеном уже создан. '
                    'Он будет перезаписан. Вы уверены?'
                )
            )
            if confirm:
                new_token = click.prompt(
                    'Введите токен', hide_input=True
                )
                self.config.update_github_token(new_token)
            else:
                return
        else:
            token = click.prompt(
                text='Введите GitHub токен', hide_input=True
            )
            self.config.set_github_token(token)

        _echo_success('Токен успешно сохранен')

import subprocess

import click

from ._styled import _echo_error, _echo_success
from .config import Config
from .exceptions import ConfigNotFound
from .parser import Parser


class Command:
    def __init__(self, path: str, output_filename: str, samples: int):
        self.path = path
        self.output_filename = output_filename
        self.samples = samples
        self.config = Config()

    def run(self):
        command = self._echo_pipe() + self._run_py_spy()
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True
            )
        except ConfigNotFound:
            _echo_error('ОШИБКА: Файл конфигурации не существует, необходимо запустить: pyflame-ai config init')
            return
        if result.returncode == 0:
            _echo_success('Сбор данных прошел успешно')
        else:
            if 'No such file or directory' in result.stderr:
                _echo_error('Файл не найден')
                return
            elif 'py-spy: command not found' in result.stderr:
                _echo_error('ОШИБКА: Необходимо установить пакет py-spy')
                return
            elif 'no password was provided' in result.stderr:
                _echo_error('ОШИБКА: Неверный пароль sudo')
                c = Config()
                password_prompt = click.prompt(text='Введите пароль sudo', hide_input=True)
                c.update_password(password_prompt)
                return self.run()
            else:
                _echo_error('Произошла непредвиденная ошибка')
                _echo_error(result.stderr)
                return

        _parser = Parser(self.output_filename)
        _parser.parse()

    def _echo_pipe(self):
        password = self.config.get_password()
        return f'echo "{password}" | '

    def _run_py_spy(self):
        return f"sudo -Sk py-spy record -o {self.output_filename} --format raw -r {self.samples} -- python {self.path}"

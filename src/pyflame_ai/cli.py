import click

from .command import OpenReportCommand, RefactorCommand, SimpleRunCommand, ConfigCommand


@click.group()
def cli():
    pass


@cli.command()
def config():
    """
    Инициализирует или обновляет файл конфигурации приложения.
    """
    command = ConfigCommand()
    command.run()


@cli.command()
@click.option('--filename', '-f', default='profile_cli.txt', type=str)
@click.option('--raw', '-r', is_flag=True, default=False, type=bool)
def open_report(filename, raw):
    """
    Отображает отчёт профилирования из сохранённого файла.
    """
    command = OpenReportCommand(filename, raw)
    command.run()


@cli.command()
@click.option('--path', '-p', required=True, type=str)
@click.option('--output-filename', '-o', default='profile_cli.txt', type=str)
@click.option('--samples', '-s', default=1000, type=int)
@click.option('--api-key', required=True, type=str)
def refactor_run(path, output_filename, samples, api_key):
    """
    Выполняет профилирование кода и автоматический рефакторинг наиболее ресурсоёмкой функции.
    """
    command = RefactorCommand(path, output_filename, samples, api_key)
    command.run()


@cli.command()
@click.option('--path', '-p', required=True, type=str)
@click.option('--output-filename', '-o', default='profile_cli.txt', type=str)
@click.option('--samples', '-s', default=1000, type=int)
def simple_run(path, output_filename, samples):
    """
    Выполняет профилирование кода и выводит отчёт без применения рефакторинга.
    """
    command = SimpleRunCommand(path, output_filename, samples)
    command.run()
    command.report_renderer()

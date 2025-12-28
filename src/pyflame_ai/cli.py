#!/usr/bin/env python3
import click

from .command import Command
from .parser import print_report
from .config import Config
from ._styled import  _echo_success


@click.group()
def cli():
    pass


@cli.command()
def config():
    c = Config()
    if c.config_exist():
        confirm = click.confirm(
            click.style('Файл конфигурации с GitHub токеном уже создан. Он будет перезаписан. Вы уверены?'))
        if confirm:
            new_token = click.prompt('Введите токен', hide_input=True)
            c.update_github_token(new_token)
        else:
            return

    else:
        token = click.prompt(text='Введите GitHub токен', hide_input=True)
        c.set_github_token(token)

    _echo_success('Токен успешно сохранен')


@cli.command()
@click.option('--filename', '-f', default='profile_cli.txt', type=str)
@click.option('--raw', '-r', is_flag=True, default=False, type=bool)
def open_report(filename, raw):
    print_report(filename, raw)


@cli.command()
@click.option('--path', '-p', required=True, type=str)
@click.option('--output-filename', '-o', default='profile_cli.txt', type=str)
@click.option('--samples', '-s', default=1000, type=int)
@click.option('--api-key', required=True, type=str)
@click.option('--dry-run', is_flag=True, default=False, type=bool)
def run(path, output_filename, samples, api_key, dry_run):
    command = Command(path, output_filename, samples, api_key, dry_run=dry_run)
    command.run()

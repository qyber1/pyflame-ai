#!/usr/bin/env python3
from xmlrpc.client import Fault

import click

from .command import Command
from .parser import print_report
from .config import Config
from ._styled import _echo_warning


@click.group()
def cli():
    pass


@cli.group()
def config():
    pass


@cli.command()
@click.option('--filename', '-f', default='profile_cli.txt', type=str)
@click.option('--raw', '-r', default=False, type=bool)
def open_report(filename, raw):
    print_report(filename, raw)


@cli.command()
@click.option('--path', '-p', required=True, type=str)
@click.option('--output-filename', '-o', default='profile_cli.txt', type=str)
@click.option('--samples', '-s', default=100, type=int)
def run(path, output_filename, samples):
    command = Command(path, output_filename, samples)
    command.run()


@config.command()
def init():
    c = Config()
    if c.config_exist():
        _echo_warning('Файл конфигурации уже создан. Для обновления конфиг-файла выполните: pyflame-ai config update')
        return
    password_prompt = click.prompt(text='Введите пароль sudo', hide_input=True)
    c.set_password(password_prompt)


@config.command()
def update():
    c = Config()
    password_prompt = click.prompt(text='Введите пароль sudo', hide_input=True)
    c.update_password(password_prompt)

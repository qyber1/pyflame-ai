from pathlib import Path
from configparser import ConfigParser

from .exceptions import ConfigAlreadyExists, ConfigNotFound


class Config:

    def __init__(self):
        self._config_path = Path('~/.pyflame-ai').expanduser()
        self._config_path.mkdir(parents=True, exist_ok=True)

        self._config_file = self._config_path / 'config.ini'
        self._parser = ConfigParser()

    @property
    def file(self):
        return self._config_file

    def get_github_token(self):
        if not self.config_exist():
            raise ConfigNotFound()
        self._read_config()
        return self._parser['github']['token']

    def set_github_token(self, token):
        if self.config_exist():
            raise ConfigAlreadyExists()
        self._parser['github'] = {'token': token}
        with open(self.file, 'w') as f:
            self._parser.write(f)

    def update_github_token(self, token):
        self._parser['sudo'] = {'password': token}
        with open(self.file, 'w') as f:
            self._parser.write(f)

    def config_exist(self):
        return self._read_config()

    def _read_config(self):
        return self._parser.read(self.file)

class ConfigAlreadyExists(Exception):
    def __init__(self):
        super().__init__()


class ConfigNotFound(Exception):
    def __init__(self):
        super().__init__()

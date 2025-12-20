from click import echo, style


def _echo_error(text: str) -> None:
    echo(style(text, fg='red'))


def _echo_success(text: str) -> None:
    echo(style(text, fg='green'))


def _echo_warning(text: str) -> None:
    echo(style(text, fg='yellow'))


def _echo_usual(text: str) -> None:
    echo(text)
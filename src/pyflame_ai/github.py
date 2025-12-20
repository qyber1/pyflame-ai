import random
import string
from pathlib import Path
from typing import Optional

import libcst as cst
from git import Repo, exc
from pyflame_ai._styled import _echo_error


class FunctionFinder(cst.CSTVisitor):
    """
    Посещает узлы AST и ищет все функции с заданным именем на любом уровне вложенности.

    Атрибуты:
        name (str): Имя функции для поиска.
        nodes (list[cst.FunctionDef]): Список найденных функций с совпадающим именем.
    """

    def __init__(self, name: str):
        """
        :param name: Имя функции, которую необходимо найти
        """
        self.name = name
        self.nodes: list[cst.FunctionDef] = []

    def visit_FunctionDef(self, node: cst.FunctionDef):
        """
        Вызывается при посещении каждого определения функции в дереве CST.

        :param node: Узел FunctionDef AST
        """
        if node.name.value == self.name:
            self.nodes.append(node)


class FunctionReplacer(cst.CSTTransformer):
    """
    Трансформер AST, который заменяет все найденные функции новым определением функции.

    Атрибуты:
        target_name (str): Имя функции, которую необходимо заменить.
        new_function (cst.FunctionDef): Новый узел функции для замены.
        replaced_count (int): Счётчик заменённых функций.
    """

    def __init__(self, target_name: str, new_function: cst.FunctionDef):
        """
        :param target_name: Имя функции, которую нужно заменить
        :param new_function: Новый узел функции для вставки
        """
        self.target_name = target_name
        self.new_function = new_function
        self.replaced_count = 0

    def leave_FunctionDef(
            self,
            original_node: cst.FunctionDef,
            updated_node: cst.FunctionDef,
    ) -> cst.FunctionDef:
        """
        Заменяет узел, если имя совпадает.

        :param original_node: Оригинальный узел функции
        :param updated_node: Обновлённый узел функции после посещения дочерних элементов
        :return: Новый узел функции или оригинальный
        """
        if original_node.name.value == self.target_name:
            self.replaced_count += 1
            return self.new_function.with_changes(
                leading_lines=original_node.leading_lines
            )
        return updated_node


class GitHubRefactor:
    """
    Класс для рефакторинга функции в исходном коде Python с последующим пушем изменений в Git.

    Атрибуты:
        source (Path): Путь к исходному файлу Python.
        func_name (str): Имя функции, которую необходимо заменить.
        refactor_code (str): Новый код функции для замены.
    """

    def __init__(self, source: str, func_name: str, refactor_code: str):
        """
        :param source: Путь к исходному файлу Python
        :param func_name: Имя функции для замены
        :param refactor_code: Новый код функции
        """
        self.source = Path(source)
        self.func_name = func_name
        self.refactor_code = refactor_code

    def refactor(self, token: str) -> Optional[str]:
        """
        Основной метод для замены функции в исходном коде и пуша изменений.

        1. Читает исходный код и строит CST.
        2. Находит все функции с указанным именем.
        3. Проверяет корректность нового кода функции.
        4. Заменяет все найденные функции.
        5. Сохраняет изменения в исходный файл.
        6. Выполняет git workflow: создание ветки, коммит и пуш.
        :return: Ссылка на коммит или сообщение об ошибке
        """
        source_code = self.source.read_text(encoding="utf-8")
        module = cst.parse_module(source_code)

        finder = FunctionFinder(self.func_name)
        module.visit(finder)
        if not finder.nodes:
            return _echo_error(f"Функция '{self.func_name}' не найдена ни на одном уровне")

        new_module = cst.parse_module(self.refactor_code)
        if len(new_module.body) != 1 or not isinstance(new_module.body[0], cst.FunctionDef):
            return _echo_error("Код для замены должен содержать ровно одну функцию")
        new_func = new_module.body[0]

        transformer = FunctionReplacer(self.func_name, new_func)
        updated_module = module.visit(transformer)
        if transformer.replaced_count == 0:
            return _echo_error("Замена функции не удалась")
        return self._git_workflow(token, updated_module.code)

    def _git_workflow(self, token: str, updated_code: str) -> Optional[str]:
        """
        Создаёт уникальную ветку, коммитит изменения и пушит их в удалённый репозиторий.

        :return: Ссылка на созданный коммит в GitHub или сообщение об ошибке
        """
        try:
            repo = Repo('.')
        except exc.InvalidGitRepositoryError:
            return _echo_error("В текущей директории нет репозитория Git (.git)")

        if repo.is_dirty():
            return _echo_error("Рабочее дерево не чистое, коммит невозможен")

        self.source.write_text(updated_code, encoding="utf-8")
        rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        branch_name = f"refactor/{self.func_name}-{rand_suffix}"

        repo.git.checkout('HEAD', b=branch_name)
        repo.git.add(str(self.source))
        commit = repo.index.commit(f"Refactor function '{self.func_name}'")
        origin = repo.remote(name='origin')
        original_url = origin.url

        if token and original_url.startswith('https://github.com/'):
            auth_url = original_url.replace('https://github.com/', f'https://{token}@github.com/')
            origin.set_url(auth_url)

        with repo.git.custom_environment(
                GCM_INTERACTIVE='Never',
                GIT_TERMINAL_PROMPT='0'
        ):
            try:
                origin.push(branch_name)
            except Exception:
                return _echo_error(
                    f'Ошибка авторизации. Не удалось отправить изменения в удаленный репозиторий Обновите токен в конфигурационном файле. Вы можете посмотреть изменения локально в ветке - {branch_name}')
            finally:
                if token and original_url.startswith('https://github.com/'):
                    origin.set_url(original_url)

        url = origin.url
        if url.endswith('.git'):
            url = url[:-4]

        if url.startswith('git@'):
            parts = url.split(':', 1)
            url = f"https://github.com/{parts[1]}"

        commit_url = f"{url}/commit/{commit.hexsha}"
        return commit_url

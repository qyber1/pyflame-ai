import ast
import json
import re
from collections import defaultdict
from pathlib import Path

from pyflame_ai._styled import _echo_error, _echo_usual


class Parser:
    """
    Парсер вывода py-spy для анализа производительности Python-кода.

    Извлекает стеки вызовов, подсчитывает количество сэмплов для каждой функции и модуля,
    вычисляет приоритет оптимизации и формирует структурированный результат анализа.

    Атрибуты:
        file (str | Path): Путь к файлу с сырым выводом py-spy.
        total_samples (int): Общее количество сэмплов.
        main_module_name (str | None): Имя основного модуля.
        overhead_samples (int): Количество сэмплов, затраченных на импорт/инициализацию.
        optimization_priority (defaultdict): Распределение сэмплов по функциям для оптимизации.
        function_totals (defaultdict): Суммарные сэмплы по функциям.
        module_samples (defaultdict): Суммарные сэмплы по модулям.
        result (dict): Итоговый результат анализа.
    """

    def __init__(self, file):
        """
        :param file: Путь к файлу с выводом py-spy
        """
        self.file = file
        self.total_samples = 0
        self.main_module_name = None
        self.overhead_samples = 0

        self.optimization_priority = defaultdict(int)
        self.function_totals = defaultdict(int)
        self.module_samples = defaultdict(int)

        self.result = {}

    def _extract_target_func(self) -> bool:
        """
        Извлекает исходный код самой "тяжёлой" функции из её модуля.

        :return: True, если код функции найден и добавлен в self.result['source_code'], иначе False
        """
        try:
            module = Path(self.result['module_distribution'][0]['module'])
            func_name = self.result['function_totals'][0]['function']
        except IndexError:
            return False

        source = module.read_text(encoding="utf-8")
        lines = source.splitlines()

        tree = ast.parse(source)
        code = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == func_name:
                    start = (
                        min(d.lineno for d in node.decorator_list) - 1
                        if node.decorator_list
                        else node.lineno - 1
                    )
                    end = node.end_lineno
                    code = "\n".join(lines[start:end])
        if code is None:
            return False

        self.result['source_code'] = code
        return True

    def parse(self) -> dict:
        """
        Основной метод парсинга файла py-spy.

        1. Считывает файл построчно.
        2. Подсчитывает сэмплы по стеку вызовов.
        3. Формирует структурированный результат.
        4. Извлекает исходный код функции для рефакторинга.

        :return: dict с результатом анализа
        """
        with open(self.file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parts = line.rsplit(' ', 1)
                if len(parts) != 2:
                    continue

                stack_str, samples_str = parts

                try:
                    samples_count = int(samples_str)
                except ValueError:
                    continue

                self.total_samples += samples_count

                if self.main_module_name is None:
                    self._extract_main_module_name(stack_str)

                self._analyze_stack(stack_str, samples_count)

        self._format_result()
        if not self._extract_target_func():
            _echo_error('Не получилось найти фунцию для рефакторинга')
            return
        return self.result

    def _analyze_stack(self, stack_str, samples_count) -> None:
        """
        Анализирует стек вызовов и распределяет сэмплы между функциями и модулями.

        :param stack_str: Строковое представление стека вызовов
        :param samples_count: Количество сэмплов для этого стека
        """
        items = [item.strip() for item in stack_str.split(';') if item.strip()]

        stack_type = self._classify_stack(items)

        if stack_type == "import":
            self.overhead_samples += samples_count
            active_func = self._get_active_function(items)
            if active_func:
                func_name, module_name, line_num = active_func
                key = f"{func_name}:{line_num}"
                self.optimization_priority[key] += samples_count
                self.function_totals[func_name] += samples_count
                self.module_samples[module_name] += samples_count

        elif stack_type == "main_module_code":
            if items and items[0].startswith('<module>'):
                items = items[1:]
            if not items:
                self.overhead_samples += samples_count
            else:
                self._process_functions(items, samples_count, self.main_module_name)

        elif stack_type == "other_module":
            active_func = self._get_active_function(items)
            if active_func:
                func_name, module_name, line_num = active_func
                key = f"{func_name}:{line_num}"
                self.optimization_priority[key] += samples_count
                self.function_totals[func_name] += samples_count
                self.module_samples[module_name] += samples_count

    def _classify_stack(self, items) -> str:
        """
        Классифицирует стек вызовов на типы:
        - "import": импорт модуля
        - "main_module_code": код основного модуля
        - "other_module": код другого модуля

        :param items: список элементов стека
        :return: тип стека
        """
        if not items:
            return "unknown"

        import_patterns = [
            '_find_and_load', '_find_and_load_unlocked',
            '_load_unlocked', 'exec_module', '_call_with_frames_removed'
        ]

        for item in items:
            for pattern in import_patterns:
                if pattern in item:
                    return "import"

        first_item = items[0]
        if first_item.startswith('<module>'):
            match = re.search(r'\(([^)]+\.py):', first_item)
            if match:
                module_name = match.group(1)
                if module_name == self.main_module_name:
                    return "main_module_code"
                else:
                    return "other_module"

        return "other_module"

    def _get_active_function(self, items) -> tuple[str, str, str] | None:
        """
        Возвращает последнюю (активную) функцию в стеке вызовов.

        :param items: список элементов стека
        :return: кортеж (function_name, module_name, line_number) или None
        """
        if not items:
            return None

        last_item = items[-1]
        match = re.search(r'([^ ]+)\s+\(([^)]+)\)', last_item)
        if not match:
            return None

        func_name = match.group(1)
        location = match.group(2)

        if ':' in location:
            module_part, line_part = location.split(':', 1)
            module_name = self._clean_module_name(module_part)
            return (func_name, module_name, line_part)

        return None

    def _clean_module_name(self, module_str) -> str:
        """
        Очищает имя модуля от <frozen ...>.

        :param module_str: строка с именем модуля
        :return: очищенное имя модуля
        """
        if module_str.startswith('<frozen '):
            match = re.search(r'<frozen ([^>]+)>', module_str)
            if match:
                return match.group(1)
        return module_str

    def _process_functions(self, items, samples_count, module_name) -> None:
        """
        Обрабатывает функции из стека вызовов и распределяет сэмплы.

        :param items: элементы стека
        :param samples_count: количество сэмплов
        :param module_name: имя модуля
        """
        if not items:
            return

        active_func_info = items[-1]
        match = re.search(r'([^ ]+)\s+\([^:]+:(\d+)\)', active_func_info)
        if not match:
            return

        func_name = match.group(1)
        line_number = match.group(2)

        key = f"{func_name}:{line_number}"
        self.optimization_priority[key] += samples_count
        self.function_totals[func_name] += samples_count
        self.module_samples[module_name] += samples_count

    def _extract_main_module_name(self, stack_str) -> None:
        """
        Извлекает имя основного модуля из строки стека вызовов.

        :param stack_str: строка стека вызовов
        """
        items = [item.strip() for item in stack_str.split(';') if item.strip()]
        for item in items:
            if item.startswith('<module>'):
                match = re.search(r'\(([^)]+\.py):', item)
                if match:
                    module_name = match.group(1)
                    if not module_name.startswith('<'):
                        self.main_module_name = module_name
                        break

    def _format_result(self) -> None:
        """
        Формирует итоговый результат анализа, сортирует функции и модули по сэмплам
        и вычисляет процентное распределение.
        """
        sorted_priority = sorted(
            self.optimization_priority.items(),
            key=lambda x: x[1],
            reverse=True
        )

        sorted_totals = sorted(
            self.function_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )

        sorted_modules = sorted(
            self.module_samples.items(),
            key=lambda x: x[1],
            reverse=True
        )

        def format_percentage(samples):
            if self.total_samples == 0:
                return "0.0%"
            return f"{samples / self.total_samples * 100:.1f}%"

        self.result = {
            'summary': {
                'total_samples': self.total_samples,
                'main_module': self.main_module_name,
                'overhead_samples': self.overhead_samples,
                'overhead_percentage': format_percentage(self.overhead_samples),
                'total_modules': len(self.module_samples)
            },
            'optimization_priority': [
                {
                    'location': location,
                    'samples': samples,
                    'percentage': format_percentage(samples)
                }
                for location, samples in sorted_priority[:20]
            ],
            'function_totals': [
                {
                    'function': func,
                    'samples': samples,
                    'percentage': format_percentage(samples)
                }
                for func, samples in sorted_totals
            ],
            'module_distribution': [
                {
                    'module': module,
                    'samples': samples,
                    'percentage': format_percentage(samples)
                }
                for module, samples in sorted_modules
            ],
            'statistics': {
                'code_samples': self.total_samples - self.overhead_samples,
                'code_percentage': format_percentage(self.total_samples - self.overhead_samples),
                'import_overhead': self.overhead_samples,
                'import_percentage': format_percentage(self.overhead_samples)
            }
        }

class ReportRenderer:
    def render(self, result: dict, raw: bool = False) -> None:
        if raw:
            _echo_usual(json.dumps(result, indent=2))
            return

        _echo_usual("=" * 70)
        _echo_usual("FLAMEGRAPH ANALYSIS REPORT")
        _echo_usual("=" * 70)

        summary = result['summary']
        _echo_usual("\nSUMMARY:")
        _echo_usual(f"  • Total samples: {summary['total_samples']}")
        _echo_usual(f"  • Main module: {summary['main_module']}")
        _echo_usual(
            f"  • Import/Initialization overhead: "
            f"{summary['overhead_samples']} samples ({summary['overhead_percentage']})"
        )
        _echo_usual(f"  • Modules analyzed: {summary['total_modules']}")

        _echo_usual("\nMODULE DISTRIBUTION:")
        _echo_usual("-" * 70)
        for item in result['module_distribution']:
            _echo_usual(f"  {item['module']:30} {item['samples']:5} samples ({item['percentage']})")

        _echo_usual("\nTOP OPTIMIZATION TARGETS:")
        _echo_usual("-" * 70)
        for i, item in enumerate(result['optimization_priority'], 1):
            _echo_usual(f"{i:2}. {item['location']:25} {item['samples']:5} samples ({item['percentage']})")

        _echo_usual("\nFUNCTION TOTALS:")
        _echo_usual("-" * 70)
        for i, item in enumerate(result['function_totals'], 1):
            _echo_usual(f"{i:2}. {item['function']:20} {item['samples']:5} samples ({item['percentage']})")

        stats = result['statistics']
        _echo_usual("\nSTATISTICS:")
        _echo_usual(f"  • Code execution: {stats['code_samples']} samples ({stats['code_percentage']})")
        _echo_usual(
            f"  • Import/Initialization: "
            f"{stats['import_overhead']} samples ({stats['import_percentage']})"
        )
        _echo_usual("=" * 70)
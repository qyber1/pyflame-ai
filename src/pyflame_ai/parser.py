import re
from collections import defaultdict

import click

from pyflame_ai._styled import _echo_error, _echo_usual


class Parser:
    def __init__(self, file):
        self.file = file
        self.total_samples = 0
        self.main_module_name = None
        self.overhead_samples = 0

        # Для хранения данных
        self.optimization_priority = defaultdict(int)  # func:line -> samples
        self.function_totals = defaultdict(int)  # func -> samples
        self.module_samples = defaultdict(int)  # module -> samples

        # Результат
        self.result = {}

    def parse(self) -> dict:
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

                # Определяем основной модуль (первый <module> из dummy.py)
                if self.main_module_name is None:
                    self._extract_main_module_name(stack_str)

                # Анализируем стек
                self._analyze_stack(stack_str, samples_count)

        self._format_result()
        return self.result

    def _analyze_stack(self, stack_str, samples_count) -> None:
        """
        Анализирует стек вызовов и распределяет samples.
        """
        items = [item.strip() for item in stack_str.split(';') if item.strip()]

        # Определяем тип стека
        stack_type = self._classify_stack(items)

        if stack_type == "import":
            # Импорт модуля - считаем как overhead/initialization
            self.overhead_samples += samples_count

            # Но также можем учитывать активную функцию в импортируемом модуле
            active_func = self._get_active_function(items)
            if active_func:
                func_name, module_name, line_num = active_func
                # Учитываем как функцию из импортируемого модуля
                key = f"{func_name}:{line_num}"
                self.optimization_priority[key] += samples_count
                self.function_totals[func_name] += samples_count
                self.module_samples[module_name] += samples_count

        elif stack_type == "main_module_code":
            # Код основного модуля
            # Удаляем <module> из основного модуля
            if items and items[0].startswith('<module>'):
                items = items[1:]

            if not items:
                # Только <module> - initialization overhead
                self.overhead_samples += samples_count
            else:
                # Обрабатываем функции
                self._process_functions(items, samples_count, self.main_module_name)

        elif stack_type == "other_module":
            # Код из другого модуля (не импорт)
            active_func = self._get_active_function(items)
            if active_func:
                func_name, module_name, line_num = active_func
                # Учитываем как функцию из другого модуля
                key = f"{func_name}:{line_num}"
                self.optimization_priority[key] += samples_count
                self.function_totals[func_name] += samples_count
                self.module_samples[module_name] += samples_count

    def _classify_stack(self, items) -> str:
        """
        Классифицирует стек вызовов:
        - "import": импорт модуля (содержит importlib)
        - "main_module_code": код основного модуля
        - "other_module": код другого модуля
        """
        if not items:
            return "unknown"

        # Проверяем на импорт (содержит importlib функции)
        import_patterns = [
            '_find_and_load', '_find_and_load_unlocked',
            '_load_unlocked', 'exec_module', '_call_with_frames_removed'
        ]

        for item in items:
            for pattern in import_patterns:
                if pattern in item:
                    return "import"

        # Проверяем основной модуль
        first_item = items[0]
        if first_item.startswith('<module>'):
            # Извлекаем имя модуля
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
        Возвращает активную функцию (последнюю в стеке).
        Возвращает (function_name, module_name, line_number)
        """
        if not items:
            return None

        # Берем последний элемент стека
        last_item = items[-1]

        # Парсим функцию
        match = re.search(r'([^ ]+)\s+\(([^)]+)\)', last_item)
        if not match:
            return None

        func_name = match.group(1)
        location = match.group(2)  # "dummy2.py:4" или "<frozen importlib._bootstrap>:1360"

        # Разделяем module:line
        if ':' in location:
            module_part, line_part = location.split(':', 1)
            # Очищаем имя модуля (убираем <frozen ...>)
            module_name = self._clean_module_name(module_part)
            return (func_name, module_name, line_part)

        return None

    def _clean_module_name(self, module_str) -> str:
        """Очищает имя модуля от <frozen ...>."""
        if module_str.startswith('<frozen '):
            # Извлекаем реальное имя модуля
            match = re.search(r'<frozen ([^>]+)>', module_str)
            if match:
                return match.group(1)
        return module_str

    def _process_functions(self, items, samples_count, module_name) -> None:
        """Обрабатывает функции из стека."""
        if not items:
            return

        # Берем активную функцию
        active_func_info = items[-1]
        match = re.search(r'([^ ]+)\s+\([^:]+:(\d+)\)', active_func_info)
        if not match:
            return

        func_name = match.group(1)
        line_number = match.group(2)

        # Ключ с указанием модуля для избежания конфликтов
        key = f"{func_name}:{line_number}"
        self.optimization_priority[key] += samples_count
        self.function_totals[func_name] += samples_count
        self.module_samples[module_name] += samples_count

    def _extract_main_module_name(self, stack_str) -> None:
        """Извлекает имя основного модуля."""
        items = [item.strip() for item in stack_str.split(';') if item.strip()]

        for item in items:
            if item.startswith('<module>'):
                match = re.search(r'\(([^)]+\.py):', item)
                if match:
                    module_name = match.group(1)
                    # Игнорируем <frozen> и временные модули
                    if not module_name.startswith('<'):
                        self.main_module_name = module_name
                        break

    def _format_result(self) -> None:
        """Форматирует результат."""
        # Сортируем
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
                for location, samples in sorted_priority[:20]  # топ-20
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


def print_report(filename, raw: bool = False) -> None:
    _parser = Parser(filename)
    try:
        result = _parser.parse()
    except FileNotFoundError as e:
        return _echo_error(f'Файла не существует: {e.filename}')
    if raw:
        _echo_usual(result)
        return

    _echo_usual("=" * 70)
    _echo_usual("FLAMEGRAPH ANALYSIS REPORT")
    _echo_usual("=" * 70)

    summary = result['summary']
    _echo_usual(f"\nSUMMARY:")
    _echo_usual(f"  • Total samples: {summary['total_samples']}")
    _echo_usual(f"  • Main module: {summary['main_module']}")
    _echo_usual(
        f"  • Import/Initialization overhead: {summary['overhead_samples']} samples ({summary['overhead_percentage']})")
    _echo_usual(f"  • Modules analyzed: {summary['total_modules']}")

    _echo_usual(f"\nMODULE DISTRIBUTION:")
    _echo_usual("-" * 70)
    for item in result['module_distribution']:
        _echo_usual(f"  {item['module']:30} {item['samples']:5} samples ({item['percentage']})")

    _echo_usual(f"\nTOP OPTIMIZATION TARGETS:")
    _echo_usual("-" * 70)
    for i, item in enumerate(result['optimization_priority'], 1):
        _echo_usual(f"{i:2}. {item['location']:25} {item['samples']:5} samples ({item['percentage']})")

    _echo_usual(f"\nFUNCTION TOTALS:")
    _echo_usual("-" * 70)
    for i, item in enumerate(result['function_totals'], 1):
        _echo_usual(f"{i:2}. {item['function']:20} {item['samples']:5} samples ({item['percentage']})")

    stats = result['statistics']
    _echo_usual(f"\nSTATISTICS:")
    _echo_usual(f"  • Code execution: {stats['code_samples']} samples ({stats['code_percentage']})")
    _echo_usual(f"  • Import/Initialization: {stats['import_overhead']} samples ({stats['import_percentage']})")
    _echo_usual("=" * 70)

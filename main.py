import json
import re
from collections import defaultdict


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

    def parse(self):
        """Основной метод парсинга файла с семплами."""
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

    def _analyze_stack(self, stack_str, samples_count):
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

    def _classify_stack(self, items):
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

    def _get_active_function(self, items):
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

    def _clean_module_name(self, module_str):
        """Очищает имя модуля от <frozen ...>."""
        if module_str.startswith('<frozen '):
            # Извлекаем реальное имя модуля
            match = re.search(r'<frozen ([^>]+)>', module_str)
            if match:
                return match.group(1)
        return module_str

    def _process_functions(self, items, samples_count, module_name):
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

    def _extract_main_module_name(self, stack_str):
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

    def _format_result(self):
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

    def print_report(self):
        """Выводит отчет."""
        if not self.result:
            self.parse()

        print("=" * 70)
        print("FLAMEGRAPH ANALYSIS REPORT")
        print("=" * 70)

        summary = self.result['summary']
        print(f"\nSUMMARY:")
        print(f"  • Total samples: {summary['total_samples']}")
        print(f"  • Main module: {summary['main_module']}")
        print(
            f"  • Import/Initialization overhead: {summary['overhead_samples']} samples ({summary['overhead_percentage']})")
        print(f"  • Modules analyzed: {summary['total_modules']}")

        print(f"\nMODULE DISTRIBUTION:")
        print("-" * 70)
        for item in self.result['module_distribution']:
            print(f"  {item['module']:30} {item['samples']:5} samples ({item['percentage']})")

        print(f"\nTOP OPTIMIZATION TARGETS:")
        print("-" * 70)
        for i, item in enumerate(self.result['optimization_priority'], 1):
            print(f"{i:2}. {item['location']:25} {item['samples']:5} samples ({item['percentage']})")

        print(f"\nFUNCTION TOTALS:")
        print("-" * 70)
        for i, item in enumerate(self.result['function_totals'], 1):
            print(f"{i:2}. {item['function']:20} {item['samples']:5} samples ({item['percentage']})")

        stats = self.result['statistics']
        print(f"\nSTATISTICS:")
        print(f"  • Code execution: {stats['code_samples']} samples ({stats['code_percentage']})")
        print(f"  • Import/Initialization: {stats['import_overhead']} samples ({stats['import_percentage']})")
        print("=" * 70)


# Пример использования с вашими данными
if __name__ == "__main__":
    test_data = """<module> (dummy.py:2);_find_and_load (<frozen importlib._bootstrap>:1360);_find_and_load_unlocked (<frozen importlib._bootstrap>:1331);_load_unlocked (<frozen importlib._bootstrap>:935);exec_module (<frozen importlib._bootstrap_external>:1026);_call_with_frames_removed (<frozen importlib._bootstrap>:488);<module> (dummy2.py:6);foo2 (dummy2.py:4) 627
<module> (dummy.py:18);foo (dummy.py:12) 114
<module> (dummy.py:18);foo (dummy.py:11) 89
<module> (dummy.py:18);foo (dummy.py:11);bar (dummy.py:6) 82
<module> (dummy.py:18) 204
<module> (dummy.py:2);_find_and_load (<frozen importlib._bootstrap>:1360);_find_and_load_unlocked (<frozen importlib._bootstrap>:1331);_load_unlocked (<frozen importlib._bootstrap>:935);exec_module (<frozen importlib._bootstrap_external>:1026);_call_with_frames_removed (<frozen importlib._bootstrap>:488);<module> (dummy2.py:6);foo2 (dummy2.py:3) 189
<module> (dummy.py:18);foo (dummy.py:11);bar (dummy.py:5) 176"""

    with open('test_imports.txt', 'w') as f:
        f.write(test_data)

    parser = Parser('test_imports.txt')
    result = parser.parse()
    parser.print_report()
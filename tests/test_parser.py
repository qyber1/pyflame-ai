import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from pyflame_ai.parser import Parser


class TestParser(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _create_py_spy_output(self, content: str) -> Path:
        file_path = self.tmp_path / "profile.txt"
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def _create_source_file(self, content: str) -> Path:
        file_path = self.tmp_path / "test.py"
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def test_parse_basic_profile(self):
        source = """def slow_function():
            for _ in range(10_000_000):
                pass
        """

        profile = (
            f"<module> (test.py:8);slow_function (test.py:4) 200"
        )
        profile_file = self._create_py_spy_output(profile)

        parser = Parser(profile_file)
        with patch.object(Path, "read_text", return_value=source):
            result = parser.parse()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["summary"]["total_samples"], 200)
        self.assertEqual(result["summary"]["main_module"], 'test.py')
        self.assertEqual(len(result["function_totals"]), 1)
        self.assertEqual(result["function_totals"][0]["function"], "slow_function")

    def test_parse_multiple_functions(self):
        source = textwrap.dedent(
            """def slow_function():
                for _ in range(10):
                    pass

                def fast_function():
                    return 42
        """)

        profile = (
            "<module> (test.py:10);fast_function (test.py:8) 50\n"
            "<module> (test.py:10);slow_function (test.py:4) 150"
        )

        profile_file = self._create_py_spy_output(profile)
        parser = Parser(profile_file)

        with patch.object(Path, "read_text", return_value=source):
            result = parser.parse()

        self.assertEqual(result["summary"]["total_samples"], 200)
        self.assertEqual(result["function_totals"][0]["function"], "slow_function")
        self.assertEqual(result["function_totals"][0]["samples"], 150)
        self.assertEqual(result["function_totals"][1]["function"], "fast_function")
        self.assertEqual(result["function_totals"][1]["samples"], 50)

    def test_parse_import_overhead(self):
        source = textwrap.dedent("""
               def some_function():
                   pass
           """)

        profile = "<module> (_find_and_load:1) 100"

        profile_file = self._create_py_spy_output(profile)
        parser = Parser(profile_file)

        with patch.object(Path, "read_text", return_value=source), \
            patch.object(Parser, "_extract_target_func", return_value=True):
            result = parser.parse()

        self.assertEqual(result["statistics"]["import_overhead"], 100)
        self.assertEqual(result["statistics"]["import_percentage"], '100.0%')


if __name__ == "__main__":
    unittest.main()
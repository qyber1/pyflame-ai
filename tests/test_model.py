import unittest
from unittest.mock import MagicMock, patch

from pyflame_ai.model import Client


class TestModelClient(unittest.TestCase):

    @patch("pyflame_ai.model.OpenAI")
    def test_retry_when_stop_tokens_in_response(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        first_response = MagicMock()
        first_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="```python\ndef foo(): pass"
                )
            )
        ]

        second_response = MagicMock()
        second_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="def foo(): return 42"
                )
            )
        ]

        mock_client.chat.completions.create.side_effect = [
            first_response,
            second_response,
        ]

        client = Client(api_key="fake-key")

        code = "def foo(): return 1"
        result = client.get_refactor_code(code)

        self.assertEqual(result, "def foo(): return 42")

        self.assertEqual(
            mock_client.chat.completions.create.call_count,
            2
        )

        second_call_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
        user_message = second_call_kwargs["messages"][1]["content"]

        self.assertIn("Remove any symbols", user_message)


if __name__ == "__main__":
    unittest.main()
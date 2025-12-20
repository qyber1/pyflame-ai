from typing import Optional

from openai import OpenAI

class Client:
    """
    Класс-клиент для взаимодействия с API DeepSeek.

    Предназначен для получения отрефакторенного кода Python-функций с учётом анализа
    производительности. Гарантирует соблюдение строгих правил
    форматирования и сохранение поведения функции.
    """

    _model: str = 'deepseek-chat'
    _temperature: float = 0.0
    _stop_tokens = ["```", "###", "Explanation", "Here is"]

    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    def get_refactor_code(self, code: str) -> str:
        """
        Получает отрефакторенный вариант переданной функции.

        Выполняется запрос к DeepSeek с соблюдением строгих правил:
        - сохранение имени и аргументов функции
        - отсутствие изменений в типе возвращаемого значения и побочных эффектах
        - исключение добавления декораторов и вспомогательных функций
        - корректный Python-код без комментариев, markdown и лишнего текста

        Если в ответе встречаются стоп-символы (`"```"`, `"###"`, `"Explanation"`, `"Here is"`),
        отправляется дополнительный запрос с инструкцией удалить их.

        :param code: Исходный Python-код функции
        :return: Отрефакторенный Python-код функции или None
        """
        def request_code(prompt: str) -> Optional[str]:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": """
                        You are a senior Python performance engineer.
                        You must refactor the given Python function to improve runtime performance
                        while preserving behavior exactly.

                        Strict rules:
                        - Keep the function name identical
                        - Keep the argument list identical (names, order, defaults)
                        - Do NOT add decorators
                        - Do NOT add new helper functions or classes
                        - Do NOT add or remove imports
                        - Do NOT change return type or side effects
                        - Do NOT use eval, exec, globals, or reflection
                        - The function must be compatible with CPython
                        - Output ONLY a single valid Python function
                        - No comments, no markdown, no explanations, no extra text
                        - Output plain Python source code only
                        - Use more optimal algorithms for solution
                    """},
                    {"role": "user", "content": prompt}
                ],
                stream=False,
                temperature=self._temperature,
                stop=self._stop_tokens
            )
            return response.choices[0].message.content if response.choices else None

        prompt = f"Refactor the most time-consuming function based on py-spy output to improve performance without changing behavior.\nInput:\n{code}"
        result = request_code(prompt)


        if result and any(token in result for token in self._stop_tokens):
            prompt += "\nRemove any symbols like ``` ### Explanation Here is and return only the valid Python function code."
            result = request_code(prompt)

        return result

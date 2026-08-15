import ast
import re


class CodeValidator:
    """Safely checks Python fenced blocks without executing user/model code."""

    def validate_code_blocks(self, text: str) -> str:
        pattern = r"```python\s*(.*?)\s*```"

        def replace(match):
            code = match.group(1)
            try:
                ast.parse(code)
                return f"```python\n{code}\n```"
            except SyntaxError as exc:
                # Never silently rewrite generated code. Preserve it and add a
                # small diagnostic so the model/user can correct it.
                note = f"# Shadow AI syntax note: line {exc.lineno}: {exc.msg}\n"
                return f"```python\n{note}{code}\n```"

        return re.sub(pattern, replace, text, flags=re.DOTALL | re.IGNORECASE)

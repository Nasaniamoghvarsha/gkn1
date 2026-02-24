import ast
import json
import yaml
import re
from typing import Dict, List, Any

class CodeValidator:
    """Validator for Python, YAML, and JSON code blocks."""

    def strip_markdown(self, text: str) -> str:
        """
        Strips markdown code blocks (e.g., ```python ... ```) from text.
        Returns the raw code content.
        """
        # Patterns to match:
        # ```python\n<code>\n```
        # ```\n<code>\n```
        # Just <code> if no blocks present
        
        # Regex to find content inside triple backticks
        pattern = r"```(?:\w+)?\n?(.*?)```"
        match = re.search(pattern, text, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # If no triple backticks, try single or just return stripped text
        return text.strip()

    async def validate(self, raw_code: str, language: str) -> Dict[str, Any]:
        """
        Validates the code based on the specified language.
        Returns a dict with is_valid and a list of errors.
        """
        code = self.strip_markdown(raw_code)
        
        if not code:
            return {
                "is_valid": False, 
                "errors": [{"line": 0, "message": "Empty code output"}]
            }

        language = language.lower()
        errors = []

        try:
            if language == 'python':
                ast.parse(code)
            elif language == 'yaml':
                yaml.safe_load(code)
            elif language == 'json':
                json.loads(code)
            else:
                return {
                    "is_valid": False, 
                    "errors": [{"line": 0, "message": f"Unsupported language: {language}"}]
                }
        except SyntaxError as e:
            # Python AST specific
            errors.append({
                "line": e.lineno or 0,
                "message": f"SyntaxError: {str(e)}"
            })
        except yaml.YAMLError as e:
            # YAML specific
            message = str(e)
            line = 0
            if hasattr(e, 'problem_mark'):
                line = e.problem_mark.line + 1
            errors.append({
                "line": line,
                "message": f"YAMLError: {message}"
            })
        except json.JSONDecodeError as e:
            # JSON specific
            errors.append({
                "line": e.lineno,
                "message": f"JSONError: {e.msg}"
            })
        except Exception as e:
            # General fallback
            errors.append({
                "line": 0,
                "message": f"Error: {str(e)}"
            })

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "clean_code": code # Return clean code for subsequent nodes
        }

if __name__ == "__main__":
    # Simple self-test
    import asyncio
    v = CodeValidator()
    
    async def test():
        bad_py = "```python\ndef foo()\n  print('hi')\n```"
        res = await v.validate(bad_py, "python")
        print(f"Python Test: {res}")
        
        good_yaml = "```yaml\nservices:\n  api: latest\n```"
        res = await v.validate(good_yaml, "yaml")
        print(f"YAML Test: {res}")

    asyncio.run(test())

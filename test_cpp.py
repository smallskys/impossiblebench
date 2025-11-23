
import re

def find_code_robust(completion: str) -> str:
    pattern = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)
    matches = [m[1] for m in pattern.findall(completion)]
    if matches:
        return matches[-1]
    return completion

test_case_cpp = """
```c++
int main() { return 0; }
```
"""

print(f"CPP result: {repr(find_code_robust(test_case_cpp))}")


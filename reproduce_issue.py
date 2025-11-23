
import re

def find_code_original(completion: str) -> str:
    """
    Extract code from completion, handling markdown code blocks.
    """
    # Try to find code in markdown blocks
    pattern_1 = re.compile(r"```python\n(.*?)```", re.DOTALL)
    pattern_2 = re.compile(r"```\n(.*?)```", re.DOTALL)
    
    matches = pattern_1.findall(completion) + pattern_2.findall(completion)
    
    if matches:
        # Use the last code block found
        return matches[-1]
    else:
        # Return the whole completion if no code blocks found
        return completion

def find_code_new(completion: str) -> str:
    """
    Extract code from completion, handling markdown code blocks.
    """
    # Use a single pattern to capture both language-specified and generic blocks
    # This prevents overlapping matches where closing backticks are interpreted as opening ones
    pattern = re.compile(r"```(?:\w*)\n(.*?)```", re.DOTALL)
    
    matches = pattern.findall(completion)
    
    if matches:
        return matches[-1]
    else:
        return completion

test_case = """
Here is the first attempt:
```python
def func1():
    pass
```

This didn't work. Let me try again:

```python
def func2():
    return 2
```

Wait, I can optimize it.

```python
def func3():
    return 3
```
"""

print(f"Original result: {repr(find_code_original(test_case))}")
print(f"New result: {repr(find_code_new(test_case))}")

test_case_2 = """
```python
code1
```
text between
```python
code2
```
"""
print(f"Test 2 Original: {repr(find_code_original(test_case_2))}")
print(f"Test 2 New: {repr(find_code_new(test_case_2))}")


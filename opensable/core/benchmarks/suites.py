"""
Built-in Benchmark Suites for Open-Sable.

Includes:
  - GAIASuite:      General AI Assistants benchmark (multi-step reasoning + tools)
  - SWEBenchSuite:  Software engineering tasks (code editing + testing)
  - WebArenaSuite:  Web browsing tasks (navigation + interaction)
  - ToolUseSuite:   Tool calling correctness
  - ReasoningSuite: Multi-step reasoning and math

Total: 100 tasks across all suites.
"""

from __future__ import annotations

import logging
from typing import List

from .runner import (
    BenchmarkSuite,
    BenchmarkTask,
    TaskDifficulty,
    exact_match,
    contains_match,
    numeric_match,
    multi_choice_match,
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# GAIA -- General AI Assistants (multi-step reasoning + tool use)
# Reference: https://arxiv.org/abs/2311.12983
# --------------------------------------------------------------------------- #


class GAIASuite(BenchmarkSuite):
    """
    GAIA benchmark: Tests multi-step reasoning, web search, file handling,
    and tool use.  Tasks have single, unambiguous correct answers.
    """

    @property
    def name(self) -> str:
        return "GAIA"

    def load_tasks(self) -> List[BenchmarkTask]:
        return [
            # -- Level 1: Easy (1-2 steps) --------------------------------- #
            BenchmarkTask(
                task_id="gaia_001",
                prompt="What is the capital of the country that won the 2022 FIFA World Cup?",
                expected="Buenos Aires",
                difficulty=TaskDifficulty.EASY, category="knowledge", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_002",
                prompt="How many days are there between January 15, 2024 and March 22, 2024?",
                expected="67",
                difficulty=TaskDifficulty.EASY, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_003",
                prompt="Convert 72 degrees Fahrenheit to Celsius. Give just the number rounded to 1 decimal.",
                expected="22.2",
                difficulty=TaskDifficulty.EASY, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_004",
                prompt="What programming language was created by Guido van Rossum?",
                expected="Python",
                difficulty=TaskDifficulty.EASY, category="knowledge", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_005",
                prompt="What is 17 * 23 + 45 - 12?",
                expected="424",
                difficulty=TaskDifficulty.EASY, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_006",
                prompt="What is the chemical symbol for gold?",
                expected="Au",
                difficulty=TaskDifficulty.EASY, category="knowledge", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_007",
                prompt="What is the square root of 144?",
                expected="12",
                difficulty=TaskDifficulty.EASY, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_008",
                prompt="In what year did the Berlin Wall fall?",
                expected="1989",
                difficulty=TaskDifficulty.EASY, category="knowledge", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_009",
                prompt="What is 15% of 240?",
                expected="36",
                difficulty=TaskDifficulty.EASY, category="math", timeout=60,
            ),

            # -- Level 2: Medium (3-5 steps, may need tools) --------------- #
            BenchmarkTask(
                task_id="gaia_010",
                prompt="What is the population of the largest city in Japan, expressed in millions rounded to 1 decimal? The city is the capital.",
                expected="13.9",
                difficulty=TaskDifficulty.MEDIUM, category="knowledge", timeout=90,
            ),
            BenchmarkTask(
                task_id="gaia_011",
                prompt="If you invest $10,000 at 5% annual compound interest for 3 years, how much do you have? Round to the nearest dollar.",
                expected="11576",
                difficulty=TaskDifficulty.MEDIUM, category="math", timeout=90,
            ),
            BenchmarkTask(
                task_id="gaia_012",
                prompt="Write a Python function that checks if a string is a palindrome, ignoring case and spaces. Then test it with 'A man a plan a canal Panama' and tell me the result (True or False).",
                expected="True",
                difficulty=TaskDifficulty.MEDIUM, category="code", timeout=120,
            ),
            BenchmarkTask(
                task_id="gaia_013",
                prompt="What is the SHA-256 hash of the string 'hello world'? Give just the first 8 hex characters.",
                expected="b94d27b9",
                difficulty=TaskDifficulty.MEDIUM, category="code", timeout=90,
            ),
            BenchmarkTask(
                task_id="gaia_014",
                prompt="How many prime numbers are there between 1 and 100?",
                expected="25",
                difficulty=TaskDifficulty.MEDIUM, category="math", timeout=90,
            ),
            BenchmarkTask(
                task_id="gaia_015",
                prompt="What is the GDP of Germany in trillions of USD (approximate, to 1 decimal)?",
                expected="4",
                difficulty=TaskDifficulty.MEDIUM, category="knowledge", timeout=90,
            ),
            BenchmarkTask(
                task_id="gaia_016",
                prompt="How many bytes are in 2.5 gigabytes? Give the exact number.",
                expected="2684354560",
                difficulty=TaskDifficulty.MEDIUM, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_017",
                prompt="What is the distance from the Earth to the Moon in kilometers? Round to the nearest thousand.",
                expected="384",
                difficulty=TaskDifficulty.MEDIUM, category="knowledge", timeout=60,
            ),
            BenchmarkTask(
                task_id="gaia_018",
                prompt=(
                    "If a rectangle has a perimeter of 30 cm and one side is 8 cm, "
                    "what is the area of the rectangle in square centimeters?"
                ),
                expected="56",
                difficulty=TaskDifficulty.MEDIUM, category="math", timeout=60,
            ),

            # -- Level 3: Hard (5+ steps, requires reasoning chains) ------- #
            BenchmarkTask(
                task_id="gaia_020",
                prompt=(
                    "A train leaves City A at 9:00 AM traveling at 60 mph toward City B. "
                    "Another train leaves City B at 10:00 AM traveling at 80 mph toward City A. "
                    "The cities are 280 miles apart. At what time do the trains meet? "
                    "Give the time in HH:MM AM/PM format."
                ),
                expected="11:00 AM",
                difficulty=TaskDifficulty.HARD, category="math", timeout=120,
            ),
            BenchmarkTask(
                task_id="gaia_021",
                prompt=(
                    "I have a CSV with these rows:\n"
                    "Name,Sales,Region\n"
                    "Alice,150,North\nBob,200,South\nCharlie,180,North\n"
                    "Diana,220,South\nEve,160,North\n\n"
                    "What is the average sales for the North region?"
                ),
                expected="163.3",
                difficulty=TaskDifficulty.HARD, category="data", timeout=120,
            ),
            BenchmarkTask(
                task_id="gaia_022",
                prompt=(
                    "Write Python code to find the longest common subsequence of "
                    "'ABCBDAB' and 'BDCAB'. What is the length of the LCS?"
                ),
                expected="4",
                difficulty=TaskDifficulty.HARD, category="code", timeout=120,
            ),
            BenchmarkTask(
                task_id="gaia_023",
                prompt=(
                    "In a group of 50 students, 30 study Math, 25 study Physics, "
                    "and 10 study both. How many students study neither Math nor Physics?"
                ),
                expected="5",
                difficulty=TaskDifficulty.HARD, category="math", timeout=90,
            ),
            BenchmarkTask(
                task_id="gaia_024",
                prompt=(
                    "Sort these elements by atomic number from lowest to highest: "
                    "Gold, Carbon, Iron, Helium, Silver. List them separated by commas."
                ),
                expected="Helium, Carbon, Iron, Silver, Gold",
                difficulty=TaskDifficulty.HARD, category="knowledge", timeout=90,
            ),
            BenchmarkTask(
                task_id="gaia_025",
                prompt=(
                    "A store has a 25% off sale. After the discount, there is an additional "
                    "10% loyalty discount applied. If the original price is $200, what is the "
                    "final price? Give just the number."
                ),
                expected="135",
                difficulty=TaskDifficulty.HARD, category="math", timeout=90,
            ),
            BenchmarkTask(
                task_id="gaia_026",
                prompt=(
                    "Convert the binary number 11010110 to decimal, then to hexadecimal. "
                    "What is the hexadecimal value? Give the answer with 0x prefix."
                ),
                expected="0xD6",
                difficulty=TaskDifficulty.HARD, category="math", timeout=90,
            ),
        ]

    def evaluate(self, task: BenchmarkTask, agent_answer: str) -> float:
        if task.category == "math":
            score = numeric_match(task.expected, agent_answer)
            if score == 0:
                score = contains_match(task.expected, agent_answer)
            return score
        elif task.category == "code":
            return contains_match(task.expected, agent_answer)
        else:
            score = exact_match(task.expected, agent_answer)
            if score == 0:
                score = contains_match(task.expected, agent_answer)
            return score


# --------------------------------------------------------------------------- #
# SWE-bench -- Software Engineering Tasks
# Reference: https://swe-bench.github.io/
# --------------------------------------------------------------------------- #


class SWEBenchSuite(BenchmarkSuite):
    """SWE-bench inspired tasks: code generation, debugging, and refactoring."""

    @property
    def name(self) -> str:
        return "SWE-bench"

    def load_tasks(self) -> List[BenchmarkTask]:
        return [
            BenchmarkTask(
                task_id="swe_001",
                prompt=(
                    "Fix the bug in this Python function:\n"
                    "```python\n"
                    "def fibonacci(n):\n"
                    "    if n <= 0: return 0\n"
                    "    if n == 1: return 1\n"
                    "    return fibonacci(n) + fibonacci(n - 1)\n"
                    "```\n"
                    "What should `fibonacci(n)` on the last line be changed to?"
                ),
                expected="fibonacci(n - 2)",
                difficulty=TaskDifficulty.EASY, category="debugging", timeout=60,
            ),
            BenchmarkTask(
                task_id="swe_002",
                prompt=(
                    "Write a Python function `flatten(lst)` that flattens a nested list.\n"
                    "Example: flatten([1, [2, [3, 4], 5], 6]) should return [1, 2, 3, 4, 5, 6]\n"
                    "Show the complete function."
                ),
                expected="def flatten",
                difficulty=TaskDifficulty.MEDIUM, category="generation", timeout=90,
            ),
            BenchmarkTask(
                task_id="swe_003",
                prompt=(
                    "What is the time complexity of this function?\n"
                    "```python\n"
                    "def find_pairs(arr, target):\n"
                    "    seen = set()\n"
                    "    pairs = []\n"
                    "    for num in arr:\n"
                    "        complement = target - num\n"
                    "        if complement in seen:\n"
                    "            pairs.append((complement, num))\n"
                    "        seen.add(num)\n"
                    "    return pairs\n"
                    "```\n"
                    "Answer with just the Big-O notation."
                ),
                expected="O(n)",
                difficulty=TaskDifficulty.MEDIUM, category="analysis", timeout=60,
            ),
            BenchmarkTask(
                task_id="swe_004",
                prompt=(
                    "Refactor this code to use a dictionary instead of if/elif chains:\n"
                    "```python\n"
                    "def get_day_name(num):\n"
                    "    if num == 1: return 'Monday'\n"
                    "    elif num == 2: return 'Tuesday'\n"
                    "    elif num == 3: return 'Wednesday'\n"
                    "    elif num == 4: return 'Thursday'\n"
                    "    elif num == 5: return 'Friday'\n"
                    "    elif num == 6: return 'Saturday'\n"
                    "    elif num == 7: return 'Sunday'\n"
                    "    return 'Invalid'\n"
                    "```\n"
                    "Show the refactored function."
                ),
                expected="dict",
                difficulty=TaskDifficulty.EASY, category="refactoring", timeout=60,
            ),
            BenchmarkTask(
                task_id="swe_005",
                prompt=(
                    "Write a Python class `LRUCache` with `get(key)` and `put(key, value)` methods.\n"
                    "The cache should have a maximum capacity and evict the least recently used item\n"
                    "when full. Use `collections.OrderedDict`. Show the complete class."
                ),
                expected="class LRUCache",
                difficulty=TaskDifficulty.HARD, category="generation", timeout=120,
            ),
            BenchmarkTask(
                task_id="swe_006",
                prompt=(
                    "What does this regex match? "
                    "`^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$`\n"
                    "Answer in one word."
                ),
                expected="email",
                difficulty=TaskDifficulty.EASY, category="analysis", timeout=60,
            ),
            BenchmarkTask(
                task_id="swe_007",
                prompt=(
                    "Find the SQL injection vulnerability in this code and explain how to fix it:\n"
                    "```python\n"
                    "def get_user(username):\n"
                    "    query = f\"SELECT * FROM users WHERE name = '{username}'\"\n"
                    "    return db.execute(query)\n"
                    "```\n"
                    "What should the fix use? Answer with the technique name."
                ),
                expected="parameterized",
                difficulty=TaskDifficulty.MEDIUM, category="security", timeout=60,
            ),
            BenchmarkTask(
                task_id="swe_008",
                prompt=(
                    "What is the output of this Python code?\n"
                    "```python\n"
                    "x = [1, 2, 3]\n"
                    "y = x\n"
                    "y.append(4)\n"
                    "print(len(x))\n"
                    "```\n"
                    "Give just the number."
                ),
                expected="4",
                difficulty=TaskDifficulty.EASY, category="analysis", timeout=60,
            ),
            BenchmarkTask(
                task_id="swe_009",
                prompt=(
                    "Write a Python decorator `@timer` that prints how long a function "
                    "takes to execute. It should print 'Function {name} took {seconds:.4f}s'. "
                    "Show the complete decorator."
                ),
                expected="def timer",
                difficulty=TaskDifficulty.MEDIUM, category="generation", timeout=90,
            ),
            BenchmarkTask(
                task_id="swe_010",
                prompt=(
                    "What design pattern does this code implement?\n"
                    "```python\n"
                    "class Singleton:\n"
                    "    _instance = None\n"
                    "    def __new__(cls):\n"
                    "        if cls._instance is None:\n"
                    "            cls._instance = super().__new__(cls)\n"
                    "        return cls._instance\n"
                    "```\n"
                    "Answer with just the pattern name."
                ),
                expected="Singleton",
                difficulty=TaskDifficulty.EASY, category="analysis", timeout=60,
            ),
            BenchmarkTask(
                task_id="swe_011",
                prompt=(
                    "Fix the race condition in this Python code:\n"
                    "```python\n"
                    "import threading\n"
                    "counter = 0\n"
                    "def increment():\n"
                    "    global counter\n"
                    "    for _ in range(100000):\n"
                    "        counter += 1\n"
                    "```\n"
                    "What synchronization primitive should be used? One word."
                ),
                expected="Lock",
                difficulty=TaskDifficulty.MEDIUM, category="debugging", timeout=60,
            ),
            BenchmarkTask(
                task_id="swe_012",
                prompt=(
                    "Write a Python function `merge_sorted(a, b)` that merges two sorted "
                    "lists into one sorted list without using the built-in `sort()`. "
                    "Show the function."
                ),
                expected="def merge_sorted",
                difficulty=TaskDifficulty.MEDIUM, category="generation", timeout=90,
            ),
            BenchmarkTask(
                task_id="swe_013",
                prompt="What HTTP status code indicates 'Not Found'? Just the number.",
                expected="404",
                difficulty=TaskDifficulty.EASY, category="knowledge", timeout=30,
            ),
            BenchmarkTask(
                task_id="swe_014",
                prompt=(
                    "Write a Python generator function `fibonacci_gen()` that yields "
                    "an infinite sequence of Fibonacci numbers. Show the code."
                ),
                expected="yield",
                difficulty=TaskDifficulty.HARD, category="generation", timeout=90,
            ),
            BenchmarkTask(
                task_id="swe_015",
                prompt="What is the space complexity of merge sort? Answer with Big-O notation.",
                expected="O(n)",
                difficulty=TaskDifficulty.MEDIUM, category="analysis", timeout=60,
            ),
        ]

    def evaluate(self, task: BenchmarkTask, agent_answer: str) -> float:
        return contains_match(task.expected, agent_answer)


# --------------------------------------------------------------------------- #
# WebArena -- Web Browsing Tasks
# Reference: https://webarena.dev/
# --------------------------------------------------------------------------- #


class WebArenaSuite(BenchmarkSuite):
    """
    WebArena-inspired tasks: web search, information extraction, navigation.
    These test the agent's ability to use browser/search tools.
    """

    @property
    def name(self) -> str:
        return "WebArena"

    def load_tasks(self) -> List[BenchmarkTask]:
        return [
            BenchmarkTask(
                task_id="web_001",
                prompt="Search the web for the current population of France. Give the approximate number in millions.",
                expected="68",
                difficulty=TaskDifficulty.EASY, category="search", timeout=120,
            ),
            BenchmarkTask(
                task_id="web_002",
                prompt="What is the latest stable version of Python? Just the version number.",
                expected="3.",
                difficulty=TaskDifficulty.EASY, category="search", timeout=120,
            ),
            BenchmarkTask(
                task_id="web_003",
                prompt=(
                    "Search for the GitHub repository 'IdeoaLabs/Open-Sable'. "
                    "How many stars does it have? Give an approximate number."
                ),
                expected="",
                difficulty=TaskDifficulty.MEDIUM, category="navigation", timeout=120,
                metadata={"eval_mode": "tool_use"},
            ),
            BenchmarkTask(
                task_id="web_004",
                prompt="Find the current Bitcoin price in USD. Give just the approximate number (no $ sign).",
                expected="",
                difficulty=TaskDifficulty.MEDIUM, category="search", timeout=120,
                metadata={"eval_mode": "format_check"},
            ),
            BenchmarkTask(
                task_id="web_005",
                prompt="What is the timezone offset (in hours from UTC) for Tokyo, Japan?",
                expected="+9",
                difficulty=TaskDifficulty.EASY, category="knowledge", timeout=60,
            ),
            BenchmarkTask(
                task_id="web_006",
                prompt="Search the web for 'MIT License' and tell me the year it was first written. Just the year.",
                expected="1988",
                difficulty=TaskDifficulty.MEDIUM, category="search", timeout=120,
            ),
            BenchmarkTask(
                task_id="web_007",
                prompt="Who is the current CEO of NVIDIA? Just the full name.",
                expected="Jensen Huang",
                difficulty=TaskDifficulty.EASY, category="search", timeout=120,
            ),
            BenchmarkTask(
                task_id="web_008",
                prompt="Search for the tallest building in the world and tell me its height in meters.",
                expected="828",
                difficulty=TaskDifficulty.MEDIUM, category="search", timeout=120,
            ),
            BenchmarkTask(
                task_id="web_009",
                prompt="What country has the largest land area in the world?",
                expected="Russia",
                difficulty=TaskDifficulty.EASY, category="knowledge", timeout=60,
            ),
            BenchmarkTask(
                task_id="web_010",
                prompt=(
                    "Search the web for 'Python asyncio' and tell me what the "
                    "`asyncio.gather` function does in one sentence."
                ),
                expected="",
                difficulty=TaskDifficulty.MEDIUM, category="search", timeout=120,
                metadata={"eval_mode": "tool_use"},
            ),
            BenchmarkTask(
                task_id="web_011",
                prompt="Search for the speed of light in meters per second. Give the number.",
                expected="299792458",
                difficulty=TaskDifficulty.EASY, category="search", timeout=120,
            ),
            BenchmarkTask(
                task_id="web_012",
                prompt="What is the stock ticker symbol for Tesla? Just the symbol.",
                expected="TSLA",
                difficulty=TaskDifficulty.EASY, category="knowledge", timeout=60,
            ),
        ]

    def evaluate(self, task: BenchmarkTask, agent_answer: str) -> float:
        eval_mode = task.metadata.get("eval_mode", "")
        if eval_mode == "tool_use":
            return 1.0 if len(agent_answer.strip()) > 10 else 0.0
        elif eval_mode == "format_check":
            import re
            nums = re.findall(r'\d[\d,]*\.?\d*', agent_answer)
            return 1.0 if nums else 0.0
        elif task.expected:
            score = contains_match(task.expected, agent_answer)
            if score == 0:
                score = numeric_match(task.expected, agent_answer, tolerance=0.1)
            return score
        return 0.5


# --------------------------------------------------------------------------- #
# ToolUse -- Tool Calling Correctness
# --------------------------------------------------------------------------- #


class ToolUseSuite(BenchmarkSuite):
    """Tests the agent's ability to correctly choose and use tools."""

    @property
    def name(self) -> str:
        return "ToolUse"

    def load_tasks(self) -> List[BenchmarkTask]:
        return [
            BenchmarkTask(
                task_id="tool_001",
                prompt="What is the result of running this Python code: print(sum(range(1, 11)))",
                expected="55",
                difficulty=TaskDifficulty.EASY, category="code_execution", timeout=60,
            ),
            BenchmarkTask(
                task_id="tool_002",
                prompt=(
                    "Create a file called '/tmp/test_benchmark.txt' with the content "
                    "'Hello from benchmark' and then read it back."
                ),
                expected="Hello from benchmark",
                difficulty=TaskDifficulty.MEDIUM, category="file_ops", timeout=60,
            ),
            BenchmarkTask(
                task_id="tool_003",
                prompt="Run a web search for 'Open-Sable AI agent GitHub' and summarize what you find.",
                expected="Open-Sable",
                difficulty=TaskDifficulty.MEDIUM, category="web_search", timeout=120,
            ),
            BenchmarkTask(
                task_id="tool_004",
                prompt=(
                    "Execute this Python code and tell me the output: "
                    "import json; data = {'name': 'Sable', 'version': '1.1.0'}; "
                    "print(json.dumps(data, indent=2))"
                ),
                expected="Sable",
                difficulty=TaskDifficulty.EASY, category="code_execution", timeout=60,
            ),
            BenchmarkTask(
                task_id="tool_005",
                prompt="Calculate the factorial of 12 using Python code execution.",
                expected="479001600",
                difficulty=TaskDifficulty.MEDIUM, category="code_execution", timeout=60,
            ),
            BenchmarkTask(
                task_id="tool_006",
                prompt="List the files in the current working directory and tell me how many there are.",
                expected="",
                difficulty=TaskDifficulty.EASY, category="file_ops", timeout=60,
                metadata={"eval_mode": "tool_use"},
            ),
            BenchmarkTask(
                task_id="tool_007",
                prompt="What is today's date? Use a tool to find out, don't guess.",
                expected="",
                difficulty=TaskDifficulty.EASY, category="system", timeout=60,
                metadata={"eval_mode": "format_check"},
            ),
            BenchmarkTask(
                task_id="tool_008",
                prompt="Execute this Python code and tell me the output: print([x**2 for x in range(1, 6)])",
                expected="[1, 4, 9, 16, 25]",
                difficulty=TaskDifficulty.EASY, category="code_execution", timeout=60,
            ),
            BenchmarkTask(
                task_id="tool_009",
                prompt=(
                    "Create a file '/tmp/bench_numbers.txt' with the numbers 1 to 10, "
                    "one per line. Then read it and tell me the sum."
                ),
                expected="55",
                difficulty=TaskDifficulty.HARD, category="file_ops", timeout=90,
            ),
            BenchmarkTask(
                task_id="tool_010",
                prompt=(
                    "Use Python code execution to generate a random number between 1 and 100 "
                    "using `random.randint(1, 100)`. Tell me the number."
                ),
                expected="",
                difficulty=TaskDifficulty.EASY, category="code_execution", timeout=60,
                metadata={"eval_mode": "format_check"},
            ),
            BenchmarkTask(
                task_id="tool_011",
                prompt="Search the web for 'what is FastAPI' and give me a one-sentence description.",
                expected="",
                difficulty=TaskDifficulty.MEDIUM, category="web_search", timeout=120,
                metadata={"eval_mode": "tool_use"},
            ),
            BenchmarkTask(
                task_id="tool_012",
                prompt=(
                    "Execute Python code to sort this list and print the result: "
                    "[5, 2, 8, 1, 9, 3, 7, 4, 6]"
                ),
                expected="[1, 2, 3, 4, 5, 6, 7, 8, 9]",
                difficulty=TaskDifficulty.EASY, category="code_execution", timeout=60,
            ),
            BenchmarkTask(
                task_id="tool_013",
                prompt=(
                    "Execute Python code to find all files with '.py' extension in the "
                    "current directory. How many are there?"
                ),
                expected="",
                difficulty=TaskDifficulty.MEDIUM, category="file_ops", timeout=60,
                metadata={"eval_mode": "format_check"},
            ),
            BenchmarkTask(
                task_id="tool_014",
                prompt=(
                    "Run this Python code: import platform; print(platform.system()). "
                    "What operating system is this?"
                ),
                expected="Linux",
                difficulty=TaskDifficulty.EASY, category="system", timeout=60,
            ),
            BenchmarkTask(
                task_id="tool_015",
                prompt=(
                    "Execute Python code to calculate the first 10 Fibonacci numbers "
                    "and print them as a list."
                ),
                expected="",
                difficulty=TaskDifficulty.MEDIUM, category="code_execution", timeout=60,
                metadata={"eval_mode": "tool_use"},
            ),
        ]

    def evaluate(self, task: BenchmarkTask, agent_answer: str) -> float:
        eval_mode = task.metadata.get("eval_mode", "")
        if eval_mode == "tool_use":
            return 1.0 if len(agent_answer.strip()) > 10 else 0.0
        elif eval_mode == "format_check":
            import re
            has_number = bool(re.search(r'\d+', agent_answer))
            has_date = bool(re.search(
                r'\d{4}[-/]\d{2}[-/]\d{2}|\w+ \d{1,2},? \d{4}', agent_answer
            ))
            return 1.0 if (has_number or has_date) else 0.0
        return contains_match(task.expected, agent_answer)


# --------------------------------------------------------------------------- #
# Reasoning -- Multi-step Logical Reasoning
# --------------------------------------------------------------------------- #


class ReasoningSuite(BenchmarkSuite):
    """Tests multi-step reasoning, math, and logic capabilities."""

    @property
    def name(self) -> str:
        return "Reasoning"

    def load_tasks(self) -> List[BenchmarkTask]:
        return [
            BenchmarkTask(
                task_id="reason_001",
                prompt=(
                    "If all roses are flowers, and some flowers fade quickly, "
                    "can we conclude that some roses fade quickly? Answer Yes or No."
                ),
                expected="No",
                difficulty=TaskDifficulty.MEDIUM, category="logic", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_002",
                prompt=(
                    "A farmer has chickens and cows. There are 20 heads and 56 legs total. "
                    "How many chickens are there?"
                ),
                expected="12",
                difficulty=TaskDifficulty.MEDIUM, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_003",
                prompt=(
                    "Three switches control three light bulbs in another room. You can "
                    "only enter the room once. How do you determine which switch controls "
                    "which bulb? What is the key insight? Answer in one sentence mentioning "
                    "the physical trick."
                ),
                expected="heat",
                difficulty=TaskDifficulty.HARD, category="logic", timeout=90,
            ),
            BenchmarkTask(
                task_id="reason_004",
                prompt="What is the next number in the sequence: 2, 6, 12, 20, 30, ?",
                expected="42",
                difficulty=TaskDifficulty.MEDIUM, category="pattern", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_005",
                prompt=(
                    "A bat and a ball cost $1.10 in total. The bat costs $1.00 more "
                    "than the ball. How much does the ball cost? Give the answer in cents."
                ),
                expected="5",
                difficulty=TaskDifficulty.EASY, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_006",
                prompt=(
                    "You have 12 balls, one of which is heavier or lighter than the rest. "
                    "Using a balance scale, what is the minimum number of weighings needed "
                    "to find the odd ball and determine if it's heavier or lighter?"
                ),
                expected="3",
                difficulty=TaskDifficulty.HARD, category="logic", timeout=90,
            ),
            BenchmarkTask(
                task_id="reason_007",
                prompt="In a race, you overtake the person in 2nd place. What position are you now in?",
                expected="2nd",
                difficulty=TaskDifficulty.EASY, category="logic", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_008",
                prompt=(
                    "A lily pad doubles in size every day. If it takes 48 days to cover "
                    "the entire lake, on what day does it cover half the lake?"
                ),
                expected="47",
                difficulty=TaskDifficulty.EASY, category="logic", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_009",
                prompt="What is the sum of all integers from 1 to 1000?",
                expected="500500",
                difficulty=TaskDifficulty.MEDIUM, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_010",
                prompt=(
                    "You have 3 boxes. One has only apples, one has only oranges, and "
                    "one has both. All labels are wrong. You can pick one fruit from one "
                    "box. Which box do you pick from to determine all labels? "
                    "Answer: the box labeled ___."
                ),
                expected="both",
                difficulty=TaskDifficulty.HARD, category="logic", timeout=90,
            ),
            BenchmarkTask(
                task_id="reason_011",
                prompt=(
                    "If it takes 5 machines 5 minutes to make 5 widgets, "
                    "how long would it take 100 machines to make 100 widgets? "
                    "Answer in minutes."
                ),
                expected="5",
                difficulty=TaskDifficulty.EASY, category="logic", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_012",
                prompt=(
                    "A snail is at the bottom of a 30-foot well. Each day it climbs "
                    "3 feet, but at night it slips back 2 feet. How many days will it "
                    "take to reach the top?"
                ),
                expected="28",
                difficulty=TaskDifficulty.HARD, category="math", timeout=90,
            ),
            BenchmarkTask(
                task_id="reason_013",
                prompt="How many times does the digit 9 appear in all numbers from 1 to 100?",
                expected="20",
                difficulty=TaskDifficulty.MEDIUM, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_014",
                prompt=(
                    "There are 100 doors in a row, all initially closed. Person 1 opens "
                    "every door. Person 2 toggles every 2nd door. Person 3 toggles every "
                    "3rd door, etc. After all 100 persons, how many doors are open?"
                ),
                expected="10",
                difficulty=TaskDifficulty.HARD, category="logic", timeout=90,
            ),
            BenchmarkTask(
                task_id="reason_015",
                prompt="What is 2^10?",
                expected="1024",
                difficulty=TaskDifficulty.EASY, category="math", timeout=30,
            ),
            BenchmarkTask(
                task_id="reason_016",
                prompt=(
                    "A clock shows 3:15. What is the angle between the hour and "
                    "minute hands? Give the answer in degrees."
                ),
                expected="7.5",
                difficulty=TaskDifficulty.HARD, category="math", timeout=90,
            ),
            BenchmarkTask(
                task_id="reason_017",
                prompt=(
                    "Two fathers and two sons go fishing. They each catch one fish. "
                    "The total catch is 3 fish. How is this possible? One word answer."
                ),
                expected="grandfather",
                difficulty=TaskDifficulty.MEDIUM, category="logic", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_018",
                prompt="What is the smallest prime number greater than 50?",
                expected="53",
                difficulty=TaskDifficulty.EASY, category="math", timeout=60,
            ),
            BenchmarkTask(
                task_id="reason_019",
                prompt=(
                    "You have a 3-gallon jug and a 5-gallon jug. How do you measure "
                    "exactly 4 gallons? What is the first step? Fill which jug first?"
                ),
                expected="5",
                difficulty=TaskDifficulty.HARD, category="logic", timeout=90,
            ),
            BenchmarkTask(
                task_id="reason_020",
                prompt=(
                    "If you rearrange the letters 'CIFAIPC', you get the name of "
                    "an ocean. What is it?"
                ),
                expected="Pacific",
                difficulty=TaskDifficulty.MEDIUM, category="pattern", timeout=60,
            ),
        ]

    def evaluate(self, task: BenchmarkTask, agent_answer: str) -> float:
        if task.category == "math":
            score = numeric_match(task.expected, agent_answer)
            if score == 0:
                score = contains_match(task.expected, agent_answer)
            return score
        return contains_match(task.expected, agent_answer)

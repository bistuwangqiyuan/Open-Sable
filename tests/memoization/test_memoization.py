import unittest
from typing import List, Dict, Any
import time
import threading
from functools import lru_cache
import pytest
import random
from string import ascii_letters

class MemoizationTests(unittest.TestCase):
    """Base class for memoization tests."""

    def setUp(self):
        self.random_values = {}
        self.lock = threading.Lock()

    def generate_random_string(self, length: int = 10) -> str:
        """Generate a random string for testing."""
        with self.lock:
            key = f"rand_{len(self.random_values)}"
            if key not in self.random_values:
                self.random_values[key] = ''.join(random.choices(ascii_letters, k=length))
            return self.random_values[key]


class BasicMemoization(MemoizationTests):
    """Tests for basic memoization functionality."""

    def test_lru_cache_basics(self):
        """Test LRU cache fundamentals."""
        @lru_cache(maxsize=128)
        def add(a: int, b: int) -> int:
            return a + b

        # First call computes and caches
        result = add(2, 3)
        self.assertEqual(result, 5)
        self.assertEqual(add.cache_info().hits, 0)
        self.assertEqual(add.cache_info().misses, 1)

        # Second call uses cache
        cached_result = add(2, 3)
        self.assertEqual(cached_result, 5)
        self.assertEqual(add.cache_info().hits, 1)
        self.assertEqual(add.cache_info().misses, 1)

    def test_cache_eviction(self):
        """Test LRU cache eviction when maxsize is exceeded."""
        @lru_cache(maxsize=2)
        def identity(x: int) -> int:
            return x

        # Fill the cache
        identity(1)
        identity(2)
        self.assertEqual(identity.cache_info().currsize, 2)

        # This should evict item 1
        identity(3)
        self.assertEqual(identity.cache_info().currsize, 2)
        self.assertTrue(1 not in identity.cache)
        
    def test_cache_clear(self):
        """Test cache clearing method."""
        @lru_cache(maxsize=128)
        def multiply(a: int, b: int) -> int:
            return a * b

        # Populate cache
        multiply(2, 3)
        multiply(4, 5)
        self.assertEqual(multiply.cache_info().currsize, 2)

        # Clear cache
        multiply.cache_clear()
        self.assertEqual(multiply.cache_info().currsize, 0)


class AdvancedMemoization(MemoizationTests):
    """Tests for advanced memoization scenarios."""

    def test_thread_safety(self):
        """Test that LRU cache is thread-safe."""
        from concurrent.futures import ThreadPoolExecutor
        
        @lru_cache(maxsize=128)
        def increment(x: int) -> int:
            return x + 1

        # Shared counter
        self.shared_counter = 0
        
        def worker():
            nonlocal self.shared_counter
            for _ in range(100):
                self.shared_counter = increment(self.shared_counter)

        # Create and run threads
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker) for _ in range(4)]
            results = [future.result() for future in futures]

        # Verify final state
        self.assertEqual(self.shared_counter, 401)

    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        @lru_cache(maxsize=128)
        def is_even(x: int) -> bool:
            return x % 2 == 0

        # Initial call - miss
        self.assertFalse(is_even(3))
        self.assertEqual(is_even.cache_info().misses, 1)

        # Same input - hit
        self.assertFalse(is_even(3))
        self.assertEqual(is_even.cache_info().hits, 1)

    def test_cache_maxsize_limits(self):
        """Test that cache doesn't exceed maxsize."""
        @lru_cache(maxsize=5)
        def store_value(x: int) -> int:
            return x

        # Fill the cache
        for i in range(6):
            store_value(i)

        self.assertEqual(store_value.cache_info().currsize, 5)


class EdgeCaseMemoization(MemoizationTests):
    """Tests for memoization edge cases."""

    def test_large_input_handling(self):
        """Test memoization with large inputs."""
        @lru_cache(maxsize=128)
        def hash_string(s: str) -> int:
            return hash(s)

        # Test with very long string
        long_string = 'a' * 5000
        result = hash_string(long_string)
        self.assertEqual(result, hash(long_string))

    def test_invalid_inputs(self):
        """Test memoization with invalid inputs."""
        @lru_cache(maxsize=128)
        def process(data: Any) -> str:
            if not isinstance(data, str):
                raise ValueError("Expected string")
            return data.upper()

        # Valid input
        self.assertEqual(process("hello"), "HELLO")

        # Invalid input - should raise and not cache error
        with self.assertRaises(ValueError):
            process(123)
        
    def test_mixed_types(self):
        """Test memoization with different parameter types."""
        @lru_cache(maxsize=128)
        def combine(a: Any, b: Any) -> str:
            return str(a) + str(b)

        self.assertEqual(combine(1, 2), "12")
        self.assertEqual(combine("1", 2), "12")
        self.assertEqual(combine(1, "2"), "12")
        
    def test_keyword_arguments(self):
        """Test memoization with keyword arguments."""
        @lru_cache(maxsize=128)
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        self.assertEqual(greet("Alice"), "Hello, Alice!")
        self.assertEqual(greet("Bob", "Hi"), "Hi, Bob!")

    def test_argument_order_matters(self):
        """Test that argument order affects caching."""
        @lru_cache(maxsize=128)
        def subtract(a: int, b: int) -> int:
            return a - b

        self.assertEqual(subtract(5, 3), 2)
        self.assertEqual(subtract(3, 5), -2)
        
    def test_no_arguments(self):
        """Test memoization on functions with no arguments."""
        @lru_cache(maxsize=128)
        def get_timestamp() -> float:
            return time.time()

        # Should always return same value (approximately)
        t1 = get_timestamp()
        t2 = get_timestamp()
        self.assertAlmostEqual(t1, t2, delta=1)  # Allow 1 second drift
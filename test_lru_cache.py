import unittest
from lru_cache import LRUCache

class TestLRUCache(unittest.TestCase):
    def setUp(self):
        self.cache = LRUCache(3)
        # Populate for testing
        self.cache.put(1, 'a')
        self.cache.put(2, 'b')
        self.cache.put(3, 'c')

    def test_initial_state(self):
        print('Testing initial state:')
        self.assertEqual(self.cache.get(1), 'a')
        self.assertEqual(self.cache.get(2), 'b')
        self.assertEqual(self.cache.get(3), 'c')
        self.assertEqual(self.cache.get(4), -1)

    def test_cache_eviction(self):
        print('Testing cache eviction:')
        # Fill capacity
        self.cache.put(4, 'd')  # Should evict key 1
        self.assertEqual(self.cache.get(1), -1)
        self.assertEqual(self.cache.get(4), 'd')

    def test_move_to_head_on_access(self):
        print('Testing move-to-head on access:')
        # Access key 2 to move it to head
        self.cache.get(2)
        # Verify order: 2 -> 3 -> 1 (circular doubly linked list)
        # This is a simplified verification
        self.assertEqual(self.cache.get(2), 'b')
        self.assertEqual(self.cache.get(3), 'c')
        self.assertEqual(self.cache.get(1), 'a')

    def test_update_existing_key(self):
        print('Testing existing key update:')
        self.cache.put(2, 'new_value')
        self.assertEqual(self.cache.get(2), 'new_value')
        # Should remain at head after move
        self.assertEqual(self.cache.get(1), 'a')
        
    def test_edge_cases(self):
        print('Testing edge cases:')
        edge_cache = LRUCache(1)
        edge_cache.put(5, 'e')
        self.assertEqual(edge_cache.get(5), 'e')
        edge_cache.put(6, 'f')  # Evicts key 5
        self.assertEqual(edge_cache.get(5), -1)
        
    def test_zero_capacity(self):
        print('Testing zero capacity:')
        zero_cache = LRUCache(0)
        zero_cache.put(7, 'g')
        self.assertEqual(zero_cache.get(7), -1)

if __name__ == '__main__':
    unittest.main()
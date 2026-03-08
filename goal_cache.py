import json
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import os

class GoalReferenceCache:
    """Lightweight goal reference cache with fallback mechanisms."""

    def __init__(self, primary_capacity: int = 100, fallback_path: str = './fallback_cache.json',
                 expiration: Optional[timedelta] = timedelta(hours=1)):
        self.primary_cache: Dict[str, Any] = {}
        self.fallback_path = fallback_path
        self.expiration = expiration
        self.primary_capacity = primary_capacity
        
        # Load fallback cache on initialization
        self._load_fallback()

    def _is_expired(self, timestamp: datetime) -> bool:
        return datetime.now() > timestamp + self.expiration

    def _evict_if_full(self):
        if len(self.primary_cache) > self.primary_capacity:
            # Simple LRU eviction - this is a simplified version
            # In practice, use collections.OrderedDict for proper LRU
            self.primary_cache = dict(list(self.primary_cache.items())[-self.primary_capacity:])

    def _save_fallback(self):
        try:
            with open(self.fallback_path, 'w') as f:
                json.dump(self.primary_cache, f)
        except Exception as e:
            print(f"Fallback save failed: {str(e)}")

    def _load_fallback(self):
        try:
            if os.path.exists(self.fallback_path):
                with open(self.fallback_path, 'r') as f:
                    self.primary_cache = json.load(f)
        except Exception as e:
            print(f"Fallback load failed: {str(e)}")

    def get(self, key: str) -> Optional[Any]:
        """Get a goal reference by key, checking both primary and fallback."""
        
        # Check primary cache first
        if key in self.primary_cache:
            value = self.primary_cache[key]
            # Check if value has expiration timestamp
            if isinstance(value, dict) and 'expires_at' in value:
                if self._is_expired(value['expires_at']):
                    # Primary cache entry expired - fall back to file
                    self.primary_cache.pop(key)
                    return self._get_from_fallback(key)
            return value
        
        # Key not in primary - check fallback
        return self._get_from_fallback(key)

    def _get_from_fallback(self, key: str) -> Optional[Any]:
        """Get from fallback storage directly."""
        try:
            with open(self.fallback_path, 'r') as f:
                cache = json.load(f)
            return cache.get(key)
        except Exception as e:
            print(f"Fallback get failed: {str(e)}")
            return None

    def set(self, key: str, value: Any, expires_in: Optional[timedelta] = None):
        """Set a goal reference with optional expiration."""
        
        # Handle expiration
        if expires_in:
            value = {'data': value, 'expires_at': datetime.now() + expires_in}
        
        self.primary_cache[key] = value
        self._evict_if_full()
        self._save_fallback()

    def delete(self, key: str):
        """Delete a goal reference."""
        if key in self.primary_cache:
            del self.primary_cache[key]
        self._save_fallback()

    def clear(self):
        """Clear all cache data."""
        self.primary_cache.clear()
        self._save_fallback()

    def contains(self, key: str) -> bool:
        """Check if a key exists in the cache."""
        return key in self.primary_cache or self._get_from_fallback(key) is not None

    def list_keys(self) -> list:
        """List all keys in the cache."""
        return list(self.primary_cache.keys())

    def update_goal(self, key: str, updates: Dict[str, Any]):
        """Update specific fields of a goal reference."""
        if key in self.primary_cache:
            self.primary_cache[key].update(updates)
            self._save_fallback()

# Example usage
if __name__ == '__cache__':
    cache = GoalReferenceCache(primary_capacity=50, fallback_path='./fallback_cache.json')

    # Set some goals
    cache.set('goal:project-a', {'target': 'complete feature X', 'owner': 'team-a', 'due': '2023-12-01'},
              timedelta(hours=2))
    cache.set('goal:project-b', {'target': 'design API', 'owner': 'team-b', 'due': '2023-12-15'})

    # Access goals
    print(cache.get('goal:project-a'))
    print(cache.get('goal:project-b'))

    # Demonstrate fallback after primary expiration
    cache.set('goal:test-fallback', {'value': 'test'}, timedelta(seconds=10))
    # Simulate time passing...
    cache.delete('goal:test-fallback')
    print(cache.get('goal:test-fallback'))  # Should return None after deletion
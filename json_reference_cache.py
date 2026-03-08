from functools import lru_cache
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class JSONReferenceCache:
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._loaded: set = set()
        self._lock = threading.Lock()

    @property
    def cache(self) -> Dict[str, Any]:
        """Lazy-load all cached references if not already loaded."""
        if 'json_references' not in self._cache:
            self._load_all()\n        return self._cache['json_references']\n\
    def _load_all(self):
        """Load all JSON references from files."""
        references_to_load = [
            ('schema1', 'path/to/schema1.json'),
            ('schema2', 'path/to/schema2.json'),
            # Add more references...
        ]\n
        with self._lock:
            try:
                loaded_data = {}\n                for name, path in references_to_load:\n                    if name not in self._loaded:\n                        logger.debug(f"Loading JSON reference: {name}")
                        with open(path, 'r') as f:\n                            data = json.load(f)
                            loaded_data[name] = data\n                            self._loaded.add(name)\n                
                self._cache['json_references'] = loaded_data
                logger.info(f"Loaded {len(loaded_data)} JSON references")
            except Exception as e:\n                logger.error(f"Failed to load JSON references: {e}", exc_info=True)

    def get(self, key: str) -> Optional[Any]:
        """Get a specific JSON reference by key."""
        if 'json_references' not in self._cache:
            self._load_all()\n        return self._cache['json_references'].get(key)

    def invalidate(self, key: str):
        """Invalidate a specific cache entry."""
        if 'json_references' in self._cache:\
            self._cache['json_references'].pop(key, None)\n            self._loaded.discard(key)
        logger.debug(f"Invalidated JSON reference: {key}")

    def clear(self):
        """Clear all cached JSON references."""
        self._cache['json_references'].clear()
        self._loaded.clear()
        logger.info("Cleared all JSON references")
import threading
from functools import wraps

def lazy_property(func):
    """Decorator for lazy evaluation of properties with caching."""
    attr_name = '_' + func.__name__

    @property
    @wraps(func)
    def wrapper(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, func(self))
        return getattr(self, attr_name)

    return wrapper

class AutoLoader:
    """Automatically loads modules and caches their contents."""
    _cache = {}
    _lock = threading.Lock()

    def __init__(self, module_name):
        self.module_name = module_name
        self._loaded = False

    @lazy_property
    def data(self):
        """Loads and returns the module's data."""
        with AutoLoader._lock:
            if self.module_name not in AutoLoader._cache:
                AutoLoader._cache[self.module_name] = self._load_module()
            return AutoLoader._cache[self.module_name]

    def _load_module(self):
        """Actually loads the module from disk."""
        try:
            module = __import__(self.module_name)
            # Here we could add specific loading logic for our JSON references
            return module.__dict__
        except ImportError as e:
            raise ValueError(f"Module {self.module_name} not found") from e
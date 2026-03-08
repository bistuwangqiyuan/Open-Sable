class GoalReferenceCache:
    """Lightweight in-memory cache for goal references."""

    def __init__(self):
        """Initialize an empty cache."""
        self.cache = {}
        self.hits = 0
        self.misses = 0

    def get(self, goal_id: str) -> dict:
        """Retrieve a goal from the cache.""
        try:
            return self.cache[goal_id]
        except KeyError:
            self.misses += 1
            raise ValueError("Goal not found in cache")

    def set(self, goal_id: str, goal_data: dict):
        """Store a goal in the cache.""
        self.cache[goal_id] = goal_data

    def delete(self, goal_id: str):
        """Remove a goal from the cache.""
        if goal_id in self.cache:
            del self.cache[goal_id]

    def clear(self):
        """Clear all goals from the cache.""
        self.cache.clear()

    def stats(self):
        """Return cache statistics.""
        return {
            'total_goals': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': self.hits / max(1, self.hits + self.misses)
        }

# Example usage
if __name__ == "__main__":
    cache = GoalReferenceCache()
    # Add some goals
    cache.set("goal_1", {"id": "goal_1", "title": "Complete project plan", "status": "active"})
    cache.set("goal_2", {"id": "goal_2", "title": "Implement caching", "status": "in_progress"})

    # Test retrieval
    try:
        goal = cache.get("goal_1")
        print(f"Retrieved goal: {goal}")
    except ValueError as e:
        print(e)

    # Test non-existent goal
    try:
        goal = cache.get("nonexistent_goal")
    except ValueError as e:
        print(e)
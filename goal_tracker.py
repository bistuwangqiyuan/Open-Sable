class GoalTracker:
    """Tracks goals with unique IDs and handles missing goal errors."""

    def __init__(self):
        self.goals = {}  # ID mapping to goal data
        self.next_id = 1
        self.error_count = 0

    def add_goal(self, title, description=""):
        """Add a new goal with auto-generated ID."""
        try:
            goal = {
                'id': self.next_id,
                'title': title,
                'description': description,
                'completed': False
            }
            self.goals[goal['id']] = goal
            self.next_id += 1
            return goal
        except Exception as e:
            print(f"Error adding goal: {e}")
            raise

    def get_goal(self, goal_id):
        """Retrieve a goal by ID, handle 'not found' error."""
        try:
            return self.goals[goal_id]
        except KeyError:
            print(f"Goal with ID {goal_id} not found.")
            self.error_count += 1
            # Fallback response
            return {
                'error': True,
                'message': 'Goal not found',
                'suggested_actions': [
                    'Check the goal ID',
                    'Verify goals were added correctly',
                    'Try retrieving a different goal'
                ]
            }

    def update_goal(self, goal_id, **kwargs):
        """Update goal properties with error recovery."""
        try:
            goal = self.goals[goal_id]
            for key, value in kwargs.items():
                if key in goal:
                    goal[key] = value
            return goal
        except KeyError:
            print(f"Goal with ID {goal_id} not found for update.")
            return self.get_goal(goal_id)

    def delete_goal(self, goal_id):
        """Delete a goal with error handling."""
        try:
            del self.goals[goal_id]
            print(f"Goal {goal_id} deleted successfully.")
        except KeyError:
            print(f"Goal with ID {goal_id} not found for deletion.")

    def list_goals(self):
        """List all active goals."""
        return list(self.goals.values())


# Demonstration
if __name__ == "__main__":
    tracker = GoalTracker()

    # Add some goals
    print("Adding goals...")
    goal_1 = tracker.add_goal("Learn Python", "Complete advanced Python course")
    goal_2 = tracker.add_goal("Build projects", "Create 5 useful applications")
    invalid_goal = tracker.add_goal(None, "This should fail")

    print("\nGoal tracking demo:")
    print("Goals list:", tracker.list_goals())
    print("Specific goal:", tracker.get_goal(1))
    print("Non-existent goal:", tracker.get_goal(999))
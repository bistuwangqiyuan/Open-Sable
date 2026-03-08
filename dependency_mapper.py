class DependencyMapper:
    def __init__(self):
        self.dependencies = {}
        self.prerequisites = {}

    def declare_dependency(self, goal, prerequisite, validator):
        if goal not in self.dependencies:
            self.dependencies[goal] = []
        self.dependencies[goal].append(prerequisite)
        self.prerequisites[prerequisite] = validator

    def validate_prerequisites(self, goal):
        dependencies_to_check = self.dependencies.get(goal, [])
        validation_results = {}

        for prereq in dependencies_to_check:
            validator = self.prerequisites.get(prereq)
            if validator:
                results = validator()
                validation_results[prereq] = results

        return validation_results

    def all_prerequisites_met(self, goal):
        validations = self.validate_prerequisites(goal)
        return all(results['met'] for results in validations.values())

# Example validators
def database_connected_validator():
    return {'met': False, 'message': 'Database connection failed'}

def config_loaded_validator():
    return {'met': True, 'message': 'Configuration loaded successfully'}
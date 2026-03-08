import unittest
from dependency_mapper import DependencyMapper, database_connected_validator, config_loaded_validator

class TestDependencyMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = DependencyMapper()

    def test_dependency_declaration(self):
        self.mapper.declare_dependency("deploy_app", "database_connected", database_connected_validator)
        self.mapper.declare_dependency("deploy_app", "config_loaded", config_loaded_validator)
        
        self.assertIn("deploy_app", self.mapper.dependencies)
        self.assertEqual(len(self.mapper.dependencies["deploy_app"]), 2)

    def test_prerequisite_validation(self):
        # Mock validators for testing
        mock_validator_success = lambda: {'met': True, 'message': 'Success'}
        mock_validator_failure = lambda: {'met': False, 'message': 'Failed'}
        
        self.mapper.declare_dependency("test_goal", "success_prereq", mock_validator_success)
        self.mapper.declare_dependency("test_goal", "failure_prereq", mock_validator_failure)
        
        results = self.mapper.validate_prerequisites("test_goal")
        
        self.assertTrue(results["success_prereq"]['met'])
        self.assertFalse(results["failure_prereq"]['met'])

    def test_all_prerequisites_met(self):
        # All should succeed
        self.mapper.declare_dependency("all_good", "prereq1", lambda: {'met': True, 'message': ''})
        self.mapper.declare_dependency("all_good", "prereq2", lambda: {'met': True, 'message': ''})
        
        self.assertTrue(self.mapper.all_prerequisites_met("all_good"))

        # Mixed results
        self.mapper.declare_dependency("some_bad", "good_prereq", lambda: {'met': True, 'message': ''})
        self.mapper.declare_dependency("some_bad", "bad_prereq", lambda: {'met': False, 'message': ''})
        
        self.assertFalse(self.mapper.all_prerequisites_met("some_bad"))

if __name__ == '__main__':
    unittest.main(verbosity=2)
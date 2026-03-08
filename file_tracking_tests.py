import unittest
from datetime import datetime
import os

class FileTrackingTests(unittest.TestCase):
    """Tests for file tracking operations"""

    def setUp(self):
        self.test_dir = '/tmp/file_tracking_test'
        os.makedirs(self.test_dir, exist_ok=True)
        self.created_files = []

    def tearDown(self):
        """Clean up any files created during testing"""
        for file in self.created_files:
            try:
                os.remove(file)
            except Exception as e:
                print(f'Error removing {file}: {str(e)}')
        try:
            os.rmdir(self.test_dir)
        except Exception as e:
            print(f'Error removing test directory: {str(e)}')

    def test_file_creation_tracking(self):
        """Test that file creation is properly tracked"""
        from file_tracker import FileTracker
        tracker = FileTracker()
        
        # Create new file
        file_path = os.path.join(self.test_dir, 'test_file.txt')
        with open(file_path, 'w') as f:
            f.write('Test content')
        self.created_files.append(file_path)
        
        # Check tracking record
        records = tracker.get_records_for_file(file_path)
        self.assertTrue(records, "No tracking record found after creation")
        self.assertEqual(len(records), 1, "Multiple records created on single operation")
        record = records[0]
        self.assertEqual(record['operation'], 'create', "Wrong operation type tracked")
        self.assertAlmostEqual(record['timestamp'].timestamp(), datetime.now().timestamp(), delta=5, 
                             msg="Timestamp not within acceptable range")

    def test_move_operation_tracking(self):
        """Test that file move operations are properly tracked"""
        from file_tracker import FileTracker
        tracker = FileTracker()
        
        # Create and move file
        src_path = os.path.join(self.test_dir, 'move_test.txt')
        with open(src_path, 'w') as f:
            f.write('Content to move')
        self.created_files.append(src_path)
        
        dst_path = os.path.join(self.test_dir, 'moved_test.txt')
        
        # Perform move
        os.rename(src_path, dst_path)
        self.created_files.remove(src_path)
        self.created_files.append(dst_path)
        
        # Check tracking records
        records = tracker.get_records_for_file(dst_path)
        self.assertGreater(len(records), 1, "Move operation not recorded")
        create_record = next((r for r in records if r['operation'] == 'create'), None)
        move_record = next((r for r in records if r['operation'] == 'move'), None)
        
        self.assertIsNotNone(create_record, "Create record not found")
        self.assertIsNotNone(move_record, "Move record not found")
        
    def test_rename_operation_tracking(self):
        """Test that file rename operations are properly tracked"""
        from file_tracker import FileTracker
        tracker = FileTracker()
        
        # Create initial file
        original_path = os.path.join(self.test_dir, 'rename_original.txt')
        with open(original_path, 'w') as f:
            f.write('Renamed content')
        self.created_files.append(original_path)
        
        # Rename file
        new_path = os.path.join(self.test_dir, 'renamed_file.txt')
        os.rename(original_path, new_path)
        self.created_files.remove(original_path)
        self.created_files.append(new_path)
        
        # Check tracking
        records = tracker.get_records_for_file(new_path)
        self.assertGreater(len(records), 1, "Rename operation not recorded")
        create_record = next((r for r in records if r['operation'] == 'create'), None)
        rename_record = next((r for r in records if r['operation'] == 'rename'), None)
        
        self.assertIsNotNone(create_record, "Create record missing after rename")
        self.assertIsNotNone(rename_record, "Rename record not found")

    def test_delete_operation_tracking(self):
        """Test that file deletion is properly tracked"""
        from file_tracker import FileTracker
        tracker = FileTracker()
        
        # Create file for deletion
        delete_path = os.path.join(self.test_dir, 'delete_test.txt')
        with open(delete_path, 'w') as f:
            f.write('Deletion target')
        self.created_files.append(delete_path)
        
        # Delete file
        os.remove(delete_path)
        self.created_files.remove(delete_path)
        
        # Check tracking
        records = tracker.get_records_for_file(delete_path)
        delete_record = next((r for r in records if r['operation'] == 'delete'), None)
        
        self.assertIsNotNone(delete_record, "Delete record not found")
        self.assertAlmostEqual(
            delete_record['timestamp'].timestamp(),
            datetime.now().timestamp(),
            delta=5,
            msg="Delete timestamp mismatch"
        )

    def test_error_handling_tracking(self):
        """Test that error operations are properly tracked"""
        from file_tracker import FileTracker, FileTrackingError
        tracker = FileTracker()
        
        # Test invalid move (file doesn't exist)
        try:
            os.rename('/nonexistent/file.txt', os.path.join(self.test_dir, 'target.txt'))
        except Exception as e:
            error_type = type(e).__name__
            self.assertIn(error_type, ['FileNotFoundError', 'OSError'])
            
            # Check tracking
            records = tracker.get_records_for_file('/nonexistent/file.txt')
            error_record = next((r for r in records if r['operation'] == 'error'), None)
            
            self.assertIsNotNone(error_record, "Error record not created")
            self.assertEqual(len(records), 1, "Multiple records from single error")
            self.assertIn('exception_type', error_record, "Missing exception type in error record")
            self.assertIn('traceback', error_record, "Missing traceback in error record")

    def test_multiple_operation_tracking(self):
        """Test that multiple operations are tracked accurately"""
        from file_tracker import FileTracker
        tracker = FileTracker()
        
        # Create tracker instance
        tracker.create_tracker()  # Ensure tracker is initialized
        
        # Operation sequence:
        # 1. Create file A
        # 2. Create file B
        # 3. Move file A
        # 4. Rename file B
        
        files = []
        
        # Create file A
        file_a = os.path.join(self.test_dir, 'file_a.txt')
        with open(file_a, 'w') as f:
            f.write('File A content')
        files.append((file_a, 'create'))
        
        # Create file B
        file_b = os.path.join(self.test_dir, 'file_b.txt')
        with open(file_b, 'w') as f:
            f.write('File B content')
        files.append((file_b, 'create'))
        
        # Move file A
        file_a_new = os.path.join(self.test_dir, 'moved_file_a.txt')
        os.rename(file_a, file_a_new)
        files.append((file_a_new, 'move'))
        
        # Rename file B
        file_b_new = os.path.join(self.test_dir, 'renamed_file_b.txt')
        os.rename(file_b, file_b_new)
        files.append((file_b_new, 'rename'))
        
        # Verify all files exist at new locations
        for file_path, _ in files:
            self.assertTrue(os.path.exists(file_path), f"File {file_path} not found")
            
        # Get and verify all records
        all_records = tracker.get_all_records()
        self.assertEqual(len(all_records), 4, "Incorrect number of tracking records")
        
        # Verify record sequence matches expected operations
        operation_sequence = [r['operation'] for r in all_records]
        expected_sequence = ['create', 'create', 'move', 'rename']
        self.assertEqual(
            operation_sequence,
            expected_sequence,
            "Operation sequence mismatch"
        )

if __name__ == '__main__':
    unittest.main(verbosity=2)
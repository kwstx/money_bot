import unittest
from unittest.mock import patch
from src.telemetry import TelemetryTracker, current_time_ms

class TestTelemetryTracker(unittest.TestCase):
    
    @patch('src.telemetry.current_time_ms')
    def test_tracking_flow(self, mock_time):
        tracker = TelemetryTracker()
        
        mock_time.return_value = 1000.0
        tracker.record_receipt()
        self.assertEqual(tracker.receipt_time, 1000.0)
        
        mock_time.return_value = 1050.0
        tracker.record_parse_start()
        self.assertEqual(tracker.parse_start_time, 1050.0)
        
        mock_time.return_value = 1100.0
        tracker.record_parse_end()
        self.assertEqual(tracker.parse_end_time, 1100.0)
        
        mock_time.return_value = 1120.0
        tracker.record_pre_queue()
        self.assertEqual(tracker.pre_queue_time, 1120.0)
        
        mock_time.return_value = 1150.0
        tracker.record_post_queue()
        self.assertEqual(tracker.post_queue_time, 1150.0)
        
        data = tracker.to_dict()
        self.assertEqual(data["receipt_time"], 1000.0)
        self.assertEqual(data["parse_start_time"], 1050.0)
        self.assertEqual(data["parse_end_time"], 1100.0)
        self.assertEqual(data["pre_queue_time"], 1120.0)
        self.assertEqual(data["post_queue_time"], 1150.0)

if __name__ == '__main__':
    unittest.main()

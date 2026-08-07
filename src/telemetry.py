import time
from prometheus_client import Histogram

# Define Prometheus Histograms for latencies (in milliseconds)
# Standard buckets suitable for high-throughput messaging: 1ms to 10s
BUCKETS = (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0, float("inf"))

receipt_to_queue_latency = Histogram(
    "fomo_listener_receipt_to_queue_latency_ms",
    "Latency from webhook receipt to queue insertion attempt",
    buckets=BUCKETS
)

queue_insertion_latency = Histogram(
    "fomo_listener_queue_insertion_latency_ms",
    "Latency to insert the event into the queue/broker",
    buckets=BUCKETS
)

parse_latency = Histogram(
    "fomo_listener_parse_latency_ms",
    "Latency for parsing and canonicalizing the event",
    buckets=BUCKETS
)

end_to_end_latency = Histogram(
    "fomo_listener_e2e_latency_ms",
    "Total latency from receipt to successful publication",
    buckets=BUCKETS
)

def current_time_ms() -> float:
    return time.time() * 1000.0

class TelemetryTracker:
    """Helper to track timestamps at different stages and report metrics."""
    def __init__(self):
        self.receipt_time = None
        self.pre_queue_time = None
        self.post_queue_time = None
        self.parse_start_time = None
        self.parse_end_time = None

    def record_receipt(self):
        self.receipt_time = current_time_ms()
        
    def record_parse_start(self):
        self.parse_start_time = current_time_ms()
        
    def record_parse_end(self):
        self.parse_end_time = current_time_ms()
        if self.parse_start_time:
            parse_latency.observe(self.parse_end_time - self.parse_start_time)

    def record_pre_queue(self):
        self.pre_queue_time = current_time_ms()
        if self.receipt_time:
            receipt_to_queue_latency.observe(self.pre_queue_time - self.receipt_time)

    def record_post_queue(self):
        self.post_queue_time = current_time_ms()
        if self.pre_queue_time:
            queue_insertion_latency.observe(self.post_queue_time - self.pre_queue_time)
        if self.receipt_time:
            end_to_end_latency.observe(self.post_queue_time - self.receipt_time)

    def to_dict(self) -> dict:
        return {
            "receipt_time": self.receipt_time,
            "pre_queue_time": self.pre_queue_time,
            "post_queue_time": self.post_queue_time,
            "parse_start_time": self.parse_start_time,
            "parse_end_time": self.parse_end_time,
        }

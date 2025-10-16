# Firestore Tracker

A Python module that provides decorators to track input and output data within Python applications and automatically store them in Google Firestore.

## Features

- 📊 **Input/Output Tracking**: Automatically capture function arguments and return values
- ⏱️ **Performance Monitoring**: Track execution times for each function call
- 🚨 **Error Tracking**: Capture and store exception details when functions fail
- 🎯 **Flexible Configuration**: Customize what to track on a per-function basis
- 📦 **Batch Mode**: Optimize high-frequency function tracking with batch writes
- 🔍 **Query Interface**: Built-in methods to query and analyze tracked data
- 📈 **Statistics**: Get aggregated statistics about function executions

## Installation

```bash
pip3 install -r requirements.txt
```

## Prerequisites

- Python 3.7+
- Google Cloud project with Firestore enabled
- Authenticated Google Cloud credentials (via `gcloud auth application-default login`)

## Quick Start

### Basic Usage

```python
from firestore_tracker import track

# Use the default tracker with minimal configuration
@track()
def calculate_sum(x, y):
    return x + y

# Function calls are automatically tracked
result = calculate_sum(5, 3)
```

### Custom Configuration

```python
from firestore_tracker import FirestoreTracker

# Create a custom tracker
tracker = FirestoreTracker(
    collection_name="my_app_tracking",
    track_performance=True,
    track_errors=True
)

# Track with custom settings
@tracker.track(
    track_input=True,
    track_output=True,
    custom_fields={"version": "1.0", "environment": "production"}
)
def process_data(data):
    # Your processing logic
    return processed_data
```

## Configuration Options

### FirestoreTracker Parameters

- `collection_name` (str): Firestore collection name for storing tracking data
- `project_id` (str, optional): GCP project ID (uses default if not specified)
- `enable_tracking` (bool): Global flag to enable/disable tracking
- `track_errors` (bool): Whether to track function errors
- `track_performance` (bool): Whether to track execution time
- `batch_mode` (bool): Enable batch writes for high-frequency functions

### Decorator Parameters

- `track_input` (bool): Track function input arguments
- `track_output` (bool): Track function return values
- `custom_fields` (dict): Additional custom fields to store
- `subcollection` (str): Optional subcollection for organizing data

## Advanced Features

### Batch Mode

For high-frequency functions, enable batch mode to reduce Firestore write operations:

```python
tracker = FirestoreTracker(
    collection_name="high_freq_operations",
    batch_mode=True
)

@tracker.track()
def frequent_operation(data):
    return process(data)

# Don't forget to flush when done
tracker.flush_batch()
```

### Querying Tracked Data

```python
# Query recent executions
executions = tracker.query_executions(
    function_name="process_data",
    status="completed",
    limit=100
)

# Get statistics
stats = tracker.get_statistics("process_data")
print(f"Success rate: {stats['success_rate']}%")
print(f"Avg execution time: {stats['performance']['avg_execution_time_ms']}ms")
```

### Error Tracking

```python
@tracker.track()
def risky_operation(value):
    if value < 0:
        raise ValueError("Invalid value")
    return value * 2

# Errors are automatically tracked with full stack traces
```

### Privacy-Conscious Tracking

```python
@tracker.track(
    track_input=False,  # Don't track sensitive input
    track_output=True   # Only track output
)
def process_sensitive_data(sensitive_input):
    # Process sensitive data
    return {"status": "processed", "count": len(sensitive_input)}
```

## Data Structure

Each tracked execution creates a document in Firestore with the following structure:

```json
{
    "execution_id": "unique_hash",
    "function_name": "function_name",
    "module": "module_name",
    "timestamp": "2024-01-01T00:00:00",
    "status": "completed|failed|started",
    "input": {
        "args": [...],
        "kwargs": {...}
    },
    "output": "function_return_value",
    "execution_time_ms": 123.45,
    "error": {
        "type": "ErrorType",
        "message": "Error message",
        "traceback": "Full traceback"
    },
    "custom_fields": {...}
}
```

## Examples

See [example_usage.py](example_usage.py) for comprehensive examples including:
- Simple function tracking
- ML model prediction tracking
- Data pipeline operations
- Class method tracking
- Error handling
- Batch operations
- Querying and statistics

## Best Practices

1. **Use batch mode** for functions called frequently (>10 times/second)
2. **Disable input tracking** for functions handling sensitive data
3. **Add custom fields** to categorize and filter tracked data
4. **Use subcollections** to organize related function tracking
5. **Regularly query statistics** to monitor application performance
6. **Set up Firestore indexes** for common query patterns

## License

MIT
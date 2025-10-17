"""
Example usage of the Firestore Tracker module.

This file demonstrates various ways to use the tracking decorators.
"""

from firestore_tracker import FirestoreTracker, track
import random
import time


# Example 1: Using the default tracker with minimal configuration
@track()
def simple_calculation(x, y):
    """Simple function that adds two numbers."""
    return x + y


# Example 2: Custom tracker with specific configuration
custom_tracker = FirestoreTracker(
    collection_name="ml_model_tracking",
    track_performance=True,
    track_errors=True
)


@custom_tracker.track(
    track_input=True,
    track_output=True,
    custom_fields={"model_version": "1.0", "environment": "development"}
)
def predict_sentiment(text):
    """Mock ML model prediction function."""
    # Simulate some processing time
    time.sleep(random.uniform(0.1, 0.5))

    # Mock prediction logic
    sentiments = ["positive", "negative", "neutral"]
    confidence = random.uniform(0.5, 1.0)

    return {
        "text": text,
        "sentiment": random.choice(sentiments),
        "confidence": confidence
    }


# Example 3: Tracking only specific aspects
data_processor = FirestoreTracker(
    collection_name="data_processing",
    batch_mode=True  # Enable batch mode for high-frequency functions
)


@data_processor.track(
    track_input=False,  # Don't track input for privacy
    track_output=True,
    subcollection="transformations"
)
def transform_data(data):
    """Transform sensitive data - only track output."""
    # Simulate data transformation
    return {
        "records_processed": len(data),
        "transformation_type": "anonymization",
        "success": True
    }


# Example 4: Class method tracking
class DataPipeline:
    def __init__(self):
        self.tracker = FirestoreTracker(
            collection_name="pipeline_operations",
            track_performance=True
        )

    @property
    def track(self):
        """Property to access the tracker's track decorator."""
        return self.tracker.track

    def process(self, data):
        """Process data through the pipeline."""
        cleaned = self._clean_data(data)
        validated = self._validate_data(cleaned)
        return self._store_data(validated)

    @track()(lambda self, data: self.tracker.track()(self._clean_data)(data))
    def _clean_data(self, data):
        """Clean the input data."""
        # Mock cleaning logic
        return [item.strip() if isinstance(item, str) else item for item in data]

    def _validate_data(self, data):
        """Validate the cleaned data."""
        # Decorated inline
        @self.tracker.track(custom_fields={"step": "validation"})
        def validate():
            return [item for item in data if item]

        return validate()

    def _store_data(self, data):
        """Store the validated data."""
        @self.tracker.track(
            track_input=True,
            track_output=False,  # Don't track output for stored data
            custom_fields={"step": "storage", "storage_type": "firestore"}
        )
        def store():
            # Mock storage logic
            return {"stored_count": len(data), "timestamp": time.time()}

        return store()


# Example 5: Error tracking
error_tracker = FirestoreTracker(
    collection_name="error_tracking",
    track_errors=True
)


@error_tracker.track()
def risky_operation(value):
    """Function that might raise an error."""
    if value < 0:
        raise ValueError("Value must be non-negative")

    if value == 0:
        raise ZeroDivisionError("Cannot divide by zero")

    return 100 / value


def run_examples():
    """Run all example functions."""
    print("Running Firestore Tracker Examples...")

    # Example 1: Simple calculation
    result = simple_calculation(5, 3)
    print(f"Simple calculation result: {result}")

    # Example 2: ML prediction
    sentiment = predict_sentiment("This is a great product!")
    print(f"Sentiment prediction: {sentiment}")

    # Example 3: Data transformation
    sample_data = ["item1", "item2", "item3"]
    transform_result = transform_data(sample_data)
    print(f"Transform result: {transform_result}")

    # Flush batch if using batch mode
    data_processor.flush_batch()

    # Example 4: Pipeline processing
    pipeline = DataPipeline()
    pipeline_result = pipeline.process(["  data1  ", "data2", "", "data3"])
    print(f"Pipeline result: {pipeline_result}")

    # Example 5: Error handling
    try:
        risky_operation(10)
        print("Risky operation succeeded")
    except Exception as e:
        print(f"Risky operation failed: {e}")

    try:
        risky_operation(-5)
    except ValueError as e:
        print(f"Expected error caught: {e}")

    # Query examples
    print("\n--- Querying Tracked Executions ---")

    # Get recent executions
    recent = custom_tracker.query_executions(
        function_name="predict_sentiment",
        limit=5
    )
    print(f"Recent predictions: {len(recent)} found")

    # Get statistics
    stats = custom_tracker.get_statistics("predict_sentiment")
    print(f"Prediction statistics: {stats}")

    # Get failed executions
    errors = error_tracker.query_executions(
        status="failed",
        limit=10
    )
    print(f"Failed operations: {len(errors)} found")

    # CSV Export Examples
    print("\n--- CSV Export Examples ---")

    # Export executions to CSV file
    csv_file = custom_tracker.export_to_csv(
        filename="tracked_executions.csv",
        function_name="predict_sentiment",
        status="completed",
        limit=100
    )
    print(f"Exported executions to: {csv_file}")

    # Export to CSV string (useful for APIs or further processing)
    csv_data = custom_tracker.export_to_csv(
        function_name="predict_sentiment",
        include_input=True,
        include_output=True,
        limit=10
    )
    print(f"CSV data preview (first 200 chars): {csv_data[:200]}...")

    # Export statistics for all functions to CSV
    stats_file = custom_tracker.export_statistics_to_csv(
        filename="function_statistics.csv"
    )
    print(f"Exported statistics to: {stats_file}")

    # Export statistics for specific functions
    selected_stats = error_tracker.export_statistics_to_csv(
        function_names=["risky_operation", "simple_calculation"]
    )
    print(f"Statistics CSV preview: {selected_stats[:200]}...")


if __name__ == "__main__":
    run_examples()
"""
Firestore Data Tracker Module

A Python module that provides decorators to track input and output data
within a Python application and store it in Firestore.
"""

import functools
import json
import time
import traceback
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Union, List
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter
import hashlib
import inspect
import csv
import io


class FirestoreTracker:
    """Main class for tracking function inputs/outputs in Firestore."""

    def __init__(
        self,
        collection_name: str = "function_tracking",
        project_id: Optional[str] = None,
        enable_tracking: bool = True,
        track_errors: bool = True,
        track_performance: bool = True,
        batch_mode: bool = False
    ):
        """
        Initialize the Firestore tracker.

        Args:
            collection_name: Name of the Firestore collection to store tracking data
            project_id: GCP project ID (uses default if None)
            enable_tracking: Global flag to enable/disable tracking
            track_errors: Whether to track function errors
            track_performance: Whether to track execution time
            batch_mode: Whether to batch writes (useful for high-frequency functions)
        """
        self.collection_name = collection_name
        self.enable_tracking = enable_tracking
        self.track_errors = track_errors
        self.track_performance = track_performance
        self.batch_mode = batch_mode

        # Initialize Firestore client (uses default credentials)
        if project_id:
            self.db = firestore.Client(project=project_id)
        else:
            self.db = firestore.Client()

        self.collection = self.db.collection(collection_name)
        self.batch_buffer = []
        self.batch_size = 100

    def _serialize_data(self, data: Any) -> Any:
        """
        Serialize data for Firestore storage.

        Args:
            data: Data to serialize

        Returns:
            Serialized data safe for Firestore
        """
        if isinstance(data, (str, int, float, bool, type(None))):
            return data
        elif isinstance(data, (list, tuple)):
            return [self._serialize_data(item) for item in data]
        elif isinstance(data, dict):
            return {key: self._serialize_data(value) for key, value in data.items()}
        elif hasattr(data, "__dict__"):
            return self._serialize_data(data.__dict__)
        else:
            # For complex objects, convert to string representation
            return str(data)

    def _generate_execution_id(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """
        Generate a unique execution ID based on function name and arguments.

        Args:
            func_name: Name of the function
            args: Function arguments
            kwargs: Function keyword arguments

        Returns:
            Unique execution ID
        """
        # Create a hash of the function call for tracking
        data_str = f"{func_name}_{str(args)}_{str(kwargs)}_{datetime.utcnow().isoformat()}"
        return hashlib.md5(data_str.encode()).hexdigest()

    def track(
        self,
        track_input: bool = True,
        track_output: bool = True,
        custom_fields: Optional[Dict[str, Any]] = None,
        subcollection: Optional[str] = None
    ):
        """
        Decorator to track function inputs and outputs.

        Args:
            track_input: Whether to track function input arguments
            track_output: Whether to track function return values
            custom_fields: Additional custom fields to store
            subcollection: Optional subcollection name for organizing data

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enable_tracking:
                    return func(*args, **kwargs)

                # Prepare tracking document
                execution_id = self._generate_execution_id(func.__name__, args, kwargs)
                tracking_doc = {
                    "execution_id": execution_id,
                    "function_name": func.__name__,
                    "module": func.__module__,
                    "timestamp": datetime.utcnow(),
                    "status": "started"
                }

                # Add function signature info
                sig = inspect.signature(func)
                tracking_doc["function_signature"] = str(sig)

                # Track input if enabled
                if track_input:
                    tracking_doc["input"] = {
                        "args": self._serialize_data(args),
                        "kwargs": self._serialize_data(kwargs)
                    }

                # Add custom fields if provided
                if custom_fields:
                    tracking_doc["custom_fields"] = self._serialize_data(custom_fields)

                # Track performance metrics
                start_time = time.time() if self.track_performance else None

                try:
                    # Execute the function
                    result = func(*args, **kwargs)

                    # Track output if enabled
                    if track_output:
                        tracking_doc["output"] = self._serialize_data(result)

                    tracking_doc["status"] = "completed"

                    return result

                except Exception as e:
                    # Track errors if enabled
                    if self.track_errors:
                        tracking_doc["status"] = "failed"
                        tracking_doc["error"] = {
                            "type": type(e).__name__,
                            "message": str(e),
                            "traceback": traceback.format_exc()
                        }
                    raise

                finally:
                    # Add performance metrics
                    if self.track_performance and start_time:
                        tracking_doc["execution_time_ms"] = (time.time() - start_time) * 1000

                    # Store in Firestore
                    try:
                        if subcollection:
                            # Store in subcollection
                            self.collection.document(func.__name__).collection(
                                subcollection
                            ).document(execution_id).set(tracking_doc)
                        else:
                            # Store in main collection
                            if self.batch_mode:
                                self._add_to_batch(tracking_doc)
                            else:
                                self.collection.document(execution_id).set(tracking_doc)
                    except Exception as store_error:
                        # Log storage errors but don't interrupt function execution
                        print(f"Error storing tracking data: {store_error}")

            return wrapper
        return decorator

    def _add_to_batch(self, document: Dict[str, Any]):
        """
        Add document to batch buffer for batch writing.

        Args:
            document: Document to add to batch
        """
        self.batch_buffer.append(document)

        if len(self.batch_buffer) >= self.batch_size:
            self.flush_batch()

    def flush_batch(self):
        """Flush the batch buffer to Firestore."""
        if not self.batch_buffer:
            return

        batch = self.db.batch()

        for doc in self.batch_buffer:
            doc_ref = self.collection.document(doc["execution_id"])
            batch.set(doc_ref, doc)

        batch.commit()
        self.batch_buffer = []

    def query_executions(
        self,
        function_name: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> list:
        """
        Query tracked executions from Firestore.

        Args:
            function_name: Filter by function name
            status: Filter by status (started, completed, failed)
            start_time: Filter by minimum timestamp
            end_time: Filter by maximum timestamp
            limit: Maximum number of results

        Returns:
            List of execution documents
        """
        query = self.collection

        if function_name:
            query = query.where(filter=FieldFilter("function_name", "==", function_name))

        if status:
            query = query.where(filter=FieldFilter("status", "==", status))

        if start_time:
            query = query.where(filter=FieldFilter("timestamp", ">=", start_time))

        if end_time:
            query = query.where(filter=FieldFilter("timestamp", "<=", end_time))

        query = query.order_by("timestamp", direction=firestore.Query.DESCENDING)
        query = query.limit(limit)

        results = []
        for doc in query.stream():
            data = doc.to_dict()
            data["document_id"] = doc.id
            results.append(data)

        return results

    def get_statistics(self, function_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics for tracked functions.

        Args:
            function_name: Optional function name to filter by

        Returns:
            Dictionary containing statistics
        """
        query = self.collection

        if function_name:
            query = query.where(filter=FieldFilter("function_name", "==", function_name))

        # Get aggregation data
        total_count = 0
        completed_count = 0
        failed_count = 0
        total_execution_time = 0
        execution_times = []

        for doc in query.stream():
            data = doc.to_dict()
            total_count += 1

            if data.get("status") == "completed":
                completed_count += 1
            elif data.get("status") == "failed":
                failed_count += 1

            if "execution_time_ms" in data:
                exec_time = data["execution_time_ms"]
                total_execution_time += exec_time
                execution_times.append(exec_time)

        stats = {
            "total_executions": total_count,
            "completed": completed_count,
            "failed": failed_count,
            "success_rate": (completed_count / total_count * 100) if total_count > 0 else 0
        }

        if execution_times:
            stats["performance"] = {
                "avg_execution_time_ms": total_execution_time / len(execution_times),
                "min_execution_time_ms": min(execution_times),
                "max_execution_time_ms": max(execution_times)
            }

        return stats

    def export_to_csv(
        self,
        filename: Optional[str] = None,
        function_name: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
        include_input: bool = True,
        include_output: bool = True,
        include_errors: bool = True
    ) -> str:
        """
        Export tracked executions to CSV format.

        Args:
            filename: Optional filename to save CSV to. If None, returns CSV string
            function_name: Filter by function name
            status: Filter by status (started, completed, failed)
            start_time: Filter by minimum timestamp
            end_time: Filter by maximum timestamp
            limit: Maximum number of results to export
            include_input: Whether to include input data in export
            include_output: Whether to include output data in export
            include_errors: Whether to include error details in export

        Returns:
            CSV string if filename is None, otherwise path to saved file
        """
        # Query executions with filters
        executions = self.query_executions(
            function_name=function_name,
            status=status,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

        if not executions:
            return "No executions found matching the criteria."

        # Prepare CSV fields
        fieldnames = [
            'execution_id', 'function_name', 'module', 'timestamp',
            'status', 'execution_time_ms'
        ]

        if include_input:
            fieldnames.extend(['input_args', 'input_kwargs'])

        if include_output:
            fieldnames.append('output')

        if include_errors:
            fieldnames.extend(['error_type', 'error_message'])

        # Add custom fields if they exist
        custom_field_names = set()
        for exec_data in executions:
            if 'custom_fields' in exec_data:
                custom_field_names.update(exec_data['custom_fields'].keys())

        for field in sorted(custom_field_names):
            fieldnames.append(f'custom_{field}')

        # Create CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for exec_data in executions:
            row = {
                'execution_id': exec_data.get('execution_id', ''),
                'function_name': exec_data.get('function_name', ''),
                'module': exec_data.get('module', ''),
                'timestamp': exec_data.get('timestamp', ''),
                'status': exec_data.get('status', ''),
                'execution_time_ms': exec_data.get('execution_time_ms', '')
            }

            if include_input and 'input' in exec_data:
                row['input_args'] = json.dumps(exec_data['input'].get('args', []))
                row['input_kwargs'] = json.dumps(exec_data['input'].get('kwargs', {}))

            if include_output and 'output' in exec_data:
                row['output'] = json.dumps(exec_data.get('output', ''))

            if include_errors and 'error' in exec_data:
                row['error_type'] = exec_data['error'].get('type', '')
                row['error_message'] = exec_data['error'].get('message', '')

            # Add custom fields
            if 'custom_fields' in exec_data:
                for field, value in exec_data['custom_fields'].items():
                    row[f'custom_{field}'] = value

            writer.writerow(row)

        csv_content = output.getvalue()
        output.close()

        if filename:
            with open(filename, 'w', newline='') as f:
                f.write(csv_content)
            return filename
        else:
            return csv_content

    def export_statistics_to_csv(
        self,
        filename: Optional[str] = None,
        function_names: Optional[List[str]] = None
    ) -> str:
        """
        Export statistics for tracked functions to CSV format.

        Args:
            filename: Optional filename to save CSV to. If None, returns CSV string
            function_names: List of function names to get statistics for.
                          If None, gets stats for all unique function names.

        Returns:
            CSV string if filename is None, otherwise path to saved file
        """
        # If no function names provided, get all unique function names
        if function_names is None:
            all_executions = self.query_executions(limit=10000)
            function_names = list(set(
                exec_data.get('function_name')
                for exec_data in all_executions
                if exec_data.get('function_name')
            ))

        # Prepare CSV
        fieldnames = [
            'function_name', 'total_executions', 'completed', 'failed',
            'success_rate', 'avg_execution_time_ms', 'min_execution_time_ms',
            'max_execution_time_ms'
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for func_name in sorted(function_names):
            stats = self.get_statistics(func_name)

            row = {
                'function_name': func_name,
                'total_executions': stats.get('total_executions', 0),
                'completed': stats.get('completed', 0),
                'failed': stats.get('failed', 0),
                'success_rate': f"{stats.get('success_rate', 0):.2f}%"
            }

            if 'performance' in stats:
                perf = stats['performance']
                row.update({
                    'avg_execution_time_ms': f"{perf.get('avg_execution_time_ms', 0):.2f}",
                    'min_execution_time_ms': f"{perf.get('min_execution_time_ms', 0):.2f}",
                    'max_execution_time_ms': f"{perf.get('max_execution_time_ms', 0):.2f}"
                })

            writer.writerow(row)

        csv_content = output.getvalue()
        output.close()

        if filename:
            with open(filename, 'w', newline='') as f:
                f.write(csv_content)
            return filename
        else:
            return csv_content


# Create a default tracker instance for convenience
default_tracker = FirestoreTracker()

# Export convenient decorator
track = default_tracker.track
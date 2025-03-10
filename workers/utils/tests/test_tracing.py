"""
Tests for the tracing module to ensure trace context is properly propagated
across synchronous and asynchronous boundaries.
"""

import asyncio
import logging
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from utils.tracing import (
    TracingContextManager,
    capture_context,
    extract_trace_context_from_payload,
    generate_trace_id,
    get_account_id,
    get_job_id,
    get_lead_id,
    get_task_name,
    get_trace_context,
    get_trace_id,
    inject_trace_context_to_payload,
    restore_context,
    set_trace_context,
    TraceContextFilter
)
from utils.async_utils import to_thread, run_in_thread


class TestTracing(unittest.TestCase):
    """Test suite for the tracing module."""

    def setUp(self):
        """Reset trace context between tests."""
        # Clear trace context
        set_trace_context(None, None, None, None, None)

    def test_generate_trace_id(self):
        """Test generating a unique trace ID."""
        trace_id1 = generate_trace_id()
        trace_id2 = generate_trace_id()
        
        self.assertIsNotNone(trace_id1)
        self.assertIsNotNone(trace_id2)
        self.assertNotEqual(trace_id1, trace_id2)

    def test_set_get_trace_context(self):
        """Test setting and getting trace context values."""
        # Set values
        trace_id = "test-trace-id"
        job_id = "test-job-id"
        account_id = "test-account-id"
        lead_id = "test-lead-id"
        task_name = "test-task"
        
        set_trace_context(trace_id, job_id, account_id, lead_id, task_name)
        
        # Verify values
        self.assertEqual(get_trace_id(), trace_id)
        self.assertEqual(get_job_id(), job_id)
        self.assertEqual(get_account_id(), account_id)
        self.assertEqual(get_lead_id(), lead_id)
        self.assertEqual(get_task_name(), task_name)
        
        # Verify full context
        context = get_trace_context()
        self.assertEqual(context["trace_id"], trace_id)
        self.assertEqual(context["job_id"], job_id)
        self.assertEqual(context["account_id"], account_id)
        self.assertEqual(context["lead_id"], lead_id)
        self.assertEqual(context["task_name"], task_name)

    def test_context_manager(self):
        """Test the tracing context manager."""
        # Set initial values
        set_trace_context("initial-trace", "initial-job", "initial-account", "initial-lead", "initial-task")
        
        # Use context manager to temporarily change values
        with TracingContextManager(
            trace_id="temp-trace",
            job_id="temp-job",
            account_id="temp-account",
            lead_id="temp-lead",
            task_name="temp-task"
        ):
            # Verify temporary values
            self.assertEqual(get_trace_id(), "temp-trace")
            self.assertEqual(get_job_id(), "temp-job")
            self.assertEqual(get_account_id(), "temp-account")
            self.assertEqual(get_lead_id(), "temp-lead")
            self.assertEqual(get_task_name(), "temp-task")
        
        # Verify values are restored
        self.assertEqual(get_trace_id(), "initial-trace")
        self.assertEqual(get_job_id(), "initial-job")
        self.assertEqual(get_account_id(), "initial-account")
        self.assertEqual(get_lead_id(), "initial-lead")
        self.assertEqual(get_task_name(), "initial-task")

    def test_capture_restore_context(self):
        """Test capturing and restoring context."""
        # Set initial values
        set_trace_context("trace1", "job1", "account1", "lead1", "task1")
        
        # Capture context
        context = capture_context()
        
        # Change values
        set_trace_context("trace2", "job2", "account2", "lead2", "task2")
        
        # Verify new values
        self.assertEqual(get_trace_id(), "trace2")
        
        # Restore original context
        restore_context(context)
        
        # Verify restored values
        self.assertEqual(get_trace_id(), "trace1")
        self.assertEqual(get_job_id(), "job1")
        self.assertEqual(get_account_id(), "account1")
        self.assertEqual(get_lead_id(), "lead1")
        self.assertEqual(get_task_name(), "task1")

    def test_extract_context_from_payload(self):
        """Test extracting context from a payload."""
        payload = {
            "trace_id": "payload-trace",
            "job_id": "payload-job",
            "account_id": "payload-account",
            "lead_id": "payload-lead",
            "task_name": "payload-task",
            "other_field": "other-value"
        }
        
        context = extract_trace_context_from_payload(payload)
        
        self.assertEqual(context["trace_id"], "payload-trace")
        self.assertEqual(context["job_id"], "payload-job")
        self.assertEqual(context["account_id"], "payload-account")
        self.assertEqual(context["lead_id"], "payload-lead")
        self.assertEqual(context["task_name"], "payload-task")
        self.assertNotIn("other_field", context)

    def test_inject_context_to_payload(self):
        """Test injecting context into a payload."""
        # Set context values
        set_trace_context("inject-trace", "inject-job", "inject-account", "inject-lead", "inject-task")
        
        # Create payload
        payload = {"existing": "value"}
        
        # Inject context
        enhanced_payload = inject_trace_context_to_payload(payload)
        
        # Verify original payload is untouched
        self.assertEqual(payload, {"existing": "value"})
        
        # Verify enhanced payload has context
        self.assertEqual(enhanced_payload["existing"], "value")
        self.assertEqual(enhanced_payload["trace_id"], "inject-trace")
        self.assertEqual(enhanced_payload["job_id"], "inject-job")
        self.assertEqual(enhanced_payload["account_id"], "inject-account")
        self.assertEqual(enhanced_payload["lead_id"], "inject-lead")
        self.assertEqual(enhanced_payload["task_name"], "inject-task")

    def test_trace_context_filter(self):
        """Test the logging filter for adding trace context to log records."""
        # Set context values
        set_trace_context("log-trace", "log-job", "log-account", "log-lead", "log-task")
        
        # Create a filter
        filter = TraceContextFilter()
        
        # Create a mock log record - use a real logging.LogRecord instead of MagicMock
        # since the filter accesses attributes in a way that's not compatible with MagicMock
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test_file.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Apply filter
        filter.filter(record)
        
        # Verify trace context was added to record
        self.assertEqual(record.trace_id, "log-trace")
        self.assertEqual(record.job_id, "log-job")
        self.assertEqual(record.account_id, "log-account")
        self.assertEqual(record.lead_id, "log-lead")
        self.assertEqual(record.task_name, "log-task")

    def test_thread_context_propagation(self):
        """Test that context is properly propagated to threads."""
        def thread_func():
            # This should have access to the context from the main thread
            return get_trace_id()
        
        # Set context in main thread
        set_trace_context("thread-trace")
        
        # Run function in a thread, manually handling context
        with ThreadPoolExecutor() as executor:
            # Need to capture context before switching threads
            context = capture_context()
            
            # Define a function that restores context in the thread
            def run_with_context():
                restore_context(context)
                return thread_func()
            
            # Execute in thread
            future = executor.submit(run_with_context)
            result = future.result()
            
            # Verify context was propagated
            self.assertEqual(result, "thread-trace")


@pytest.mark.asyncio
async def test_async_context_propagation():
    """Test that context is properly propagated in async code."""
    # Set context in the main task
    set_trace_context("async-trace", "async-job", "async-account", "async-lead", "async-task")
    
    # Define an async function
    async def async_func():
        # This should have access to the context from the main task
        return get_trace_id()
    
    # Call the async function
    result = await async_func()
    
    # Verify context was propagated
    assert result == "async-trace"


@pytest.mark.asyncio
async def test_thread_pool_context_propagation():
    """Test that context is properly propagated to thread pools via decorator."""
    # Define a sync function to run in a thread
    def thread_function():
        # This should have the trace context from the calling coroutine
        return {
            "trace_id": get_trace_id(),
            "job_id": get_job_id(),
            "account_id": get_account_id()
        }
    
    # Apply the decorator that handles context propagation
    decorated_func = to_thread(thread_function)
    
    # Set context in the coroutine
    set_trace_context("threadpool-trace", "threadpool-job", "threadpool-account")
    
    # Call the decorated function
    result = await decorated_func()
    
    # Verify context was properly propagated to the thread
    assert result["trace_id"] == "threadpool-trace"
    assert result["job_id"] == "threadpool-job"
    assert result["account_id"] == "threadpool-account"


@pytest.mark.asyncio
async def test_run_in_thread_context_propagation():
    """Test that context is properly propagated with run_in_thread utility."""
    # Define a sync function to run in a thread
    def thread_function():
        # This should have the trace context from the calling coroutine
        return {
            "trace_id": get_trace_id(),
            "job_id": get_job_id(),
            "account_id": get_account_id()
        }
    
    # Set context in the coroutine
    set_trace_context("run-in-thread-trace", "run-in-thread-job", "run-in-thread-account")
    
    # Run the function in a thread
    result = await run_in_thread(thread_function)
    
    # Verify context was properly propagated to the thread
    assert result["trace_id"] == "run-in-thread-trace"
    assert result["job_id"] == "run-in-thread-job"
    assert result["account_id"] == "run-in-thread-account"
# Trace ID System for Workers

This system provides a way to trace job execution across our asynchronous worker system, making debugging and monitoring of production systems much easier. Every log message from a particular job will contain consistent trace information like `trace_id`, `job_id`, `account_id`, `lead_id`, and `task_name`.

## Core Features

1. **Consistent Trace Context Across Execution Boundaries**
   - Maintains trace context across async tasks
   - Preserves context through thread pool execution
   - Persists context through retry attempts

2. **Automatic Context Propagation**
   - No need to modify most existing code
   - Context automatically added to all log messages
   - Context flows naturally through async execution paths

3. **End-to-End Tracing**
   - Trace IDs propagate from initial request to task execution
   - Context passes through to callbacks sent to Django
   - Headers propagate trace IDs across service boundaries

## How to Use

### In API Routes

The trace context is automatically initialized in the HTTP middleware and propagated to handlers:

```python
# Trace ID will be set from request headers or generated automatically
@router.post("/some_endpoint")
async def handle_request(request: Request):
    # All logs in this handler will include trace context
    logger.info("Processing request")
    
    # When creating tasks, trace context is automatically included
    result = await task_manager.create_task(task_name, payload)
    
    return JSONResponse(content=result)
```

### In Task Execution

Trace context is automatically extracted from the task payload:

```python
# BaseTask.run_task() handles setting trace context from payload
async def execute(self, payload: Dict[str, Any]):
    # All logs will include trace context
    logger.info("Executing task")
    
    # Any child tasks will inherit trace context
    return result
```

### For Thread Pool Operations

Context is automatically propagated to thread pools:

```python
# Use the to_thread decorator for sync functions that need to run in a thread
@to_thread
def cpu_intensive_operation(data):
    # This function will see the same trace context as the caller
    logger.info("Processing in thread")
    return result

# For direct execution:
result = await run_in_thread(some_function, arg1, arg2)
```

### For Manual Context Handling

If needed, you can manually manipulate the trace context:

```python
# Capture the current context to restore later
context = capture_context()

# Set a new context
set_trace_context(trace_id="custom-trace", account_id="account-123")

# Use a context manager for temporary context changes
with TracingContextManager(trace_id="temp-trace"):
    # Code here sees the temporary context
    pass
# Original context is restored here

# Restore a previously captured context
restore_context(context)
```

## Query Logs in GCP

With this system, you can easily filter logs in Google Cloud Logging:

```
trace_id="abc-123"
```

or combine with other fields:

```
trace_id="abc-123" severity>=WARNING
```

or find all logs for a specific account:

```
account_id="account-456"
```

## Testing

The tracing system has comprehensive tests in `tests/test_tracing.py`. Run with:

```bash
python -m pytest workers/utils/tests/test_tracing.py -v
```
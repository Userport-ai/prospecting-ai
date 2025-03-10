"""
Tracing utility for maintaining context across asynchronous workers.
Provides a consistent way to trace job execution and propagate trace data
across async boundaries, threads, and task retries.
"""

import contextvars
import logging
import uuid
from typing import Dict, Optional, Any


# Context variables to store tracing information
trace_id_var = contextvars.ContextVar('trace_id', default=None)
job_id_var = contextvars.ContextVar('job_id', default=None)
account_id_var = contextvars.ContextVar('account_id', default=None)
lead_id_var = contextvars.ContextVar('lead_id', default=None)
task_name_var = contextvars.ContextVar('task_name', default=None)


def generate_trace_id() -> str:
    """Generate a unique trace ID."""
    return str(uuid.uuid4())


def get_trace_id() -> Optional[str]:
    """Get the current trace ID from context."""
    return trace_id_var.get()


def get_job_id() -> Optional[str]:
    """Get the current job ID from context."""
    return job_id_var.get()


def get_account_id() -> Optional[str]:
    """Get the current account ID from context."""
    return account_id_var.get()


def get_lead_id() -> Optional[str]:
    """Get the current lead ID from context."""
    return lead_id_var.get()


def get_task_name() -> Optional[str]:
    """Get the current task name from context."""
    return task_name_var.get()


def get_trace_context() -> Dict[str, Any]:
    """Get the complete trace context as a dictionary."""
    return {
        'trace_id': get_trace_id(),
        'job_id': get_job_id(),
        'account_id': get_account_id(),
        'lead_id': get_lead_id(),
        'task_name': get_task_name(),
    }


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """Set the trace ID in the current context."""
    if trace_id is None:
        trace_id = generate_trace_id()
    trace_id_var.set(trace_id)
    return trace_id


def set_job_id(job_id: Optional[str]) -> None:
    """Set the job ID in the current context."""
    job_id_var.set(job_id)


def set_account_id(account_id: Optional[str]) -> None:
    """Set the account ID in the current context."""
    account_id_var.set(account_id)


def set_lead_id(lead_id: Optional[str]) -> None:
    """Set the lead ID in the current context."""
    lead_id_var.set(lead_id)


def set_task_name(task_name: Optional[str]) -> None:
    """Set the task name in the current context."""
    task_name_var.set(task_name)


def set_trace_context(
    trace_id: Optional[str] = None,
    job_id: Optional[str] = None,
    account_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    task_name: Optional[str] = None,
) -> str:
    """Set the complete trace context."""
    trace_id = set_trace_id(trace_id)
    
    if job_id is not None:
        set_job_id(job_id)
    
    if account_id is not None:
        set_account_id(account_id)
    
    if lead_id is not None:
        set_lead_id(lead_id)
        
    if task_name is not None:
        set_task_name(task_name)
        
    return trace_id


def extract_trace_context_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract trace context from a task payload.
    Returns a dictionary with trace context fields.
    """
    context = {}
    
    if 'trace_id' in payload:
        context['trace_id'] = payload['trace_id']
        
    if 'job_id' in payload:
        context['job_id'] = payload['job_id']
        
    if 'account_id' in payload:
        context['account_id'] = payload['account_id']
        
    if 'lead_id' in payload:
        context['lead_id'] = payload['lead_id']
        
    if 'task_name' in payload:
        context['task_name'] = payload['task_name']
        
    return context


def inject_trace_context_to_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inject the current trace context into a task payload.
    """
    context = get_trace_context()
    result = payload.copy()
    
    # Only add fields that have values
    for key, value in context.items():
        if value is not None:
            result[key] = value
            
    return result


class TracingContextManager:
    """Context manager for trace context propagation."""
    
    def __init__(
        self,
        trace_id: Optional[str] = None,
        job_id: Optional[str] = None,
        account_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        task_name: Optional[str] = None,
    ):
        self.trace_id = trace_id
        self.job_id = job_id
        self.account_id = account_id
        self.lead_id = lead_id
        self.task_name = task_name
        
        # Store tokens for restoring previous context
        self.trace_id_token = None
        self.job_id_token = None
        self.account_id_token = None
        self.lead_id_token = None
        self.task_name_token = None
        
    def __enter__(self):
        # Save the current context
        if self.trace_id is not None:
            self.trace_id_token = trace_id_var.set(self.trace_id)
        
        if self.job_id is not None:
            self.job_id_token = job_id_var.set(self.job_id)
            
        if self.account_id is not None:
            self.account_id_token = account_id_var.set(self.account_id)
            
        if self.lead_id is not None:
            self.lead_id_token = lead_id_var.set(self.lead_id)
            
        if self.task_name is not None:
            self.task_name_token = task_name_var.set(self.task_name)
            
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore the previous context
        if self.trace_id_token is not None:
            trace_id_var.reset(self.trace_id_token)
            
        if self.job_id_token is not None:
            job_id_var.reset(self.job_id_token)
            
        if self.account_id_token is not None:
            account_id_var.reset(self.account_id_token)
            
        if self.lead_id_token is not None:
            lead_id_var.reset(self.lead_id_token)
            
        if self.task_name_token is not None:
            task_name_var.reset(self.task_name_token)


def capture_context():
    """Capture the current context to be restored later."""
    return {
        'trace_id': get_trace_id(),
        'job_id': get_job_id(),
        'account_id': get_account_id(),
        'lead_id': get_lead_id(),
        'task_name': get_task_name(),
    }


def restore_context(context):
    """Restore a previously captured context."""
    set_trace_context(
        trace_id=context.get('trace_id'),
        job_id=context.get('job_id'),
        account_id=context.get('account_id'),
        lead_id=context.get('lead_id'),
        task_name=context.get('task_name'),
    )


# Add tracing context to log records
class TraceContextFilter(logging.Filter):
    """Logging filter that adds trace context to log records."""
    
    def filter(self, record):
        if not hasattr(record, 'trace_id'):
            record.trace_id = get_trace_id()
            
        if not hasattr(record, 'job_id'):
            record.job_id = get_job_id()
            
        if not hasattr(record, 'account_id'):
            record.account_id = get_account_id()
            
        if not hasattr(record, 'lead_id'):
            record.lead_id = get_lead_id()
            
        if not hasattr(record, 'task_name'):
            record.task_name = get_task_name()
            
        return True
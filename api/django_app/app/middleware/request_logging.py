# In your app/middleware.py or logging_middleware.py

import logging
import time

from django.utils.deprecation import MiddlewareMixin


class RequestLoggingMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        super().__init__(get_response)
        self.logger = logging.getLogger('middleware.request')

    def process_request(self, request):
        # Store the start time in the request object
        request.start_time = time.time()
        self.logger.debug(f'[{request.method}] {request.path} - Request received')
        return None

    def process_response(self, request, response):
        # Calculate request processing time
        if hasattr(request, 'start_time'):
            processing_time = time.time() - request.start_time
            processing_time_ms = round(processing_time * 1000, 2)  # Convert to milliseconds
        else:
            processing_time_ms = 0  # Fallback if start_time wasn't set

        # Create log message with timing information
        log_message = (
            f'[{request.method}] {request.path} - '
            f'Status {response.status_code} - '
            f'Completed in {processing_time_ms}ms'
        )

        # Map status codes to appropriate log levels
        if response.status_code < 300:  # 2xx responses
            self.logger.info(log_message)
        elif response.status_code < 400:  # 3xx responses
            self.logger.debug(log_message)
        elif response.status_code < 500:  # 4xx responses
            self.logger.warning(log_message)
        else:  # 5xx responses
            self.logger.error(log_message)

        return response

    def process_exception(self, request, exception):
        # Include timing information in exception logs as well
        if hasattr(request, 'start_time'):
            processing_time = time.time() - request.start_time
            processing_time_ms = round(processing_time * 1000, 2)
            log_message = (
                f'[{request.method}] {request.path} - '
                f'Unhandled exception after {processing_time_ms}ms: {str(exception)}'
            )
        else:
            log_message = f'[{request.method}] {request.path} - Unhandled exception: {str(exception)}'

        self.logger.critical(log_message)
        return None
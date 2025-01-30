# In your app/middleware.py or create a new file logging_middleware.py

import logging

from django.utils.deprecation import MiddlewareMixin


class RequestLoggingMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        super().__init__(get_response)
        self.logger = logging.getLogger('django.request')

    def process_request(self, request):
        # Debug level for detailed request information
        self.logger.debug(f'[{request.method}] {request.path} - Request received')
        return None

    def process_response(self, request, response):
        # Map status codes to appropriate log levels
        if response.status_code < 300:  # 2xx responses
            self.logger.info(f'[{request.method}] {request.path} - Status {response.status_code}')
        elif response.status_code < 400:  # 3xx responses
            self.logger.debug(f'[{request.method}] {request.path} - Status {response.status_code}')
        elif response.status_code < 500:  # 4xx responses
            self.logger.warning(f'[{request.method}] {request.path} - Status {response.status_code}')
        else:  # 5xx responses
            self.logger.error(f'[{request.method}] {request.path} - Status {response.status_code}')
        return response

    def process_exception(self, request, exception):
        # Critical level for unhandled exceptions
        self.logger.critical(f'[{request.method}] {request.path} - Unhandled exception: {str(exception)}')
        return None
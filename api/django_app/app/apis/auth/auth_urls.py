from django.urls import re_path
from .auth_apis import auth_hello

authurlpatterns = [
    re_path(
       r'^auth/hello', auth_hello, name='auth_hello'
    ),
]
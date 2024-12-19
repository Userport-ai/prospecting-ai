from django.urls import re_path
from .auth_apis import auth_hello, auth_hello_with_firebase

authurlpatterns = [
    re_path(
       r'^auth/hello$', auth_hello, name='auth_hello',
    ),
    re_path(
        r'^auth/hello_with_auth$', auth_hello_with_firebase, name='auth_hello'
    ),
]
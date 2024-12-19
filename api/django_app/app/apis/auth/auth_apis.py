from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .auth_decorators import login_required


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def auth_hello(request):
    return Response("Hello World", status=200)


@api_view(['GET', 'POST'])
@login_required
def auth_hello_with_firebase(request):
    return Response("Hello World with Firebase Auth!", status=200)

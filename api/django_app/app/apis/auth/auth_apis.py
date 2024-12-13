from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET', 'POST'])
def auth_hello(request):
    return Response("Hello World", status=200)

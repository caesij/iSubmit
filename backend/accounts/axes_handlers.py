from django.http import HttpRequest
from django.shortcuts import render

def get_lockout_parameters(request_or_attempt, credentials):

    if isinstance(request_or_attempt, HttpRequest):
       is_localhost = request_or_attempt.META.get('REMOTE_ADDR') == '127.0.0.1'
    else:
       is_localhost = request_or_attempt.ip_address == '127.0.0.1'

    if is_localhost:
       return ['username']

    return ['ip_address', 'username']

def lockout_response(request, credentials, *args, **kwargs):
    return render(request, 'accounts/lockout.html', {
        'username': credentials.get('username'),
    }, status=403)
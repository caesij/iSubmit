from django.shortcuts import render

def lockout_response(request, credentials, *args, **kwargs):
    return render(request, 'accounts/lockout.html', {
        'username': credentials.get('username'),
    }, status=403)
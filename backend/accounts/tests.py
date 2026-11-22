from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from accounts.views import login_success_view, redirect_user_by_role


class LoginSuccessTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/auth/login/success/')
        self.request.user = SimpleNamespace(
            is_authenticated=True,
            role=SimpleNamespace(code='STAFF', get_code_display=lambda: 'Staff'),
        )
        self.request.session = {'show_login_success': True}

    @patch('accounts.views.render')
    @patch('accounts.views.redirect_user_by_role')
    def test_success_uses_permission_destination_and_consumes_marker(self, route, render):
        route.return_value = HttpResponseRedirect('/staff/dashboard/')
        render.return_value = HttpResponseRedirect('/rendered/')
        response = login_success_view(self.request)
        context = render.call_args.args[2]
        self.assertEqual(context['destination_url'], '/staff/dashboard/')
        self.assertEqual(context['role_name'], 'Staff')
        self.assertNotIn('show_login_success', self.request.session)
        self.assertIn('no-store', response['Cache-Control'])

    @patch('accounts.views.redirect_user_by_role')
    def test_revisit_skips_success(self, route):
        self.request.session.clear()
        route.return_value = HttpResponseRedirect('/workspace/')
        self.assertEqual(login_success_view(self.request).url, '/workspace/')

    def test_anonymous_user_must_sign_in(self):
        self.request.user.is_authenticated = False
        self.assertEqual(login_success_view(self.request).status_code, 302)
        self.assertIn(reverse('accounts:login'), login_success_view(self.request).url)

    def test_faculty_dashboard_permission_routes_correctly(self):
        user = Mock()
        user.role.is_faculty_role = True
        user.has_perm.side_effect = lambda permission: permission == 'accounts.access_faculty_dashboard'
        self.assertEqual(redirect_user_by_role(user).url, reverse('faculty_portal:dashboard'))

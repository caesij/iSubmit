from django.core import mail
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings


class AccountCreatedEmailTests(SimpleTestCase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_welcome_template_is_escaped_and_has_plain_text_alternative(self):
        context = {
            'full_name': '<Campus User>',
            'email': 'preview@example.test',
            'temporary_password': 'Demo<&Password',
            'role_name': 'Document Reviewer',
            'login_url': 'https://campus.example.test/auth/login/',
        }
        html = render_to_string('accounts/emails/account_created.html', context)
        self.assertIn('&lt;Campus User&gt;', html)
        self.assertIn('Demo&lt;&amp;Password', html)
        self.assertIn('Document Reviewer', html)
        self.assertIn('href="https://campus.example.test/auth/login/"', html)
        self.assertNotIn('<img', html)
        send_mail('Welcome', 'Plain-text credentials', 'noreply@example.test',
                  [context['email']], html_message=html)
        message = mail.outbox[0]
        self.assertEqual(message.body, 'Plain-text credentials')
        self.assertEqual(message.alternatives[0].mimetype, 'text/html')

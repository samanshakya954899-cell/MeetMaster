import os
import unittest
from unittest.mock import patch, Mock
import cloud
from backend import smtp_otp


class SMTPOTPTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'EMAIL_HOST': 'smtp.example.com', 'EMAIL_PORT': '587',
            'EMAIL_USE_TLS': 'true', 'EMAIL_HOST_USER': 'sender', 'EMAIL_HOST_PASSWORD': 'secret',
            'DEFAULT_FROM_EMAIL': 'sender@example.com', 'OTP_EXPIRY_MINUTES': '10',
            'OTP_RESEND_SECONDS': '60'}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        rng = patch.object(smtp_otp.secrets, 'randbelow', return_value=123456)
        rng.start()
        self.addCleanup(rng.stop)
        smtp_otp.PENDING.clear()
        smtp_otp.SEND_TIMES.clear()
        self.addCleanup(smtp_otp.PENDING.clear)
        self.addCleanup(smtp_otp.SEND_TIMES.clear)

    def send(self, purpose='login'):
        with patch.object(cloud, 'request', return_value={'email_otp': '12345678'}) as request, \
             patch.object(smtp_otp, 'deliver') as mail:
            result = cloud.send_code('person@example.com', purpose)
        self.assertEqual(request.call_args.args[0], '/auth/v1/admin/generate_link')
        self.assertTrue(request.call_args.kwargs['admin'])
        mail.assert_called_once_with('person@example.com', '123456', 10)
        self.assertNotIn('12345678', str(result))
        return result

    def test_delivery_resend_limit_and_single_use(self):
        self.send()
        with self.assertRaises(cloud.CloudError) as error:
            cloud.send_code('person@example.com', 'login')
        self.assertEqual(error.exception.status, 429)
        self.assertEqual(smtp_otp.verify('person@example.com', '123456', 'login', cloud.CloudError), ('person@example.com', '12345678'))
        with self.assertRaises(cloud.CloudError):
            smtp_otp.verify('person@example.com', '123456', 'login', cloud.CloudError)

    def test_wrong_code_attempt_limit(self):
        self.send()
        for _ in range(5):
            with self.assertRaises(cloud.CloudError):
                smtp_otp.verify('person@example.com', '000000', 'login', cloud.CloudError)
        with self.assertRaises(cloud.CloudError):
            smtp_otp.verify('person@example.com', '123456', 'login', cloud.CloudError)

    def test_verified_six_digits_exchange_provider_code(self):
        self.send()
        response = {'access_token': 'jwt', 'refresh_token': 'refresh', 'user': {'id': 'person'}}
        with patch.object(cloud, 'request', return_value=response) as request:
            sid, result = cloud.verify_code('person@example.com', '123456', 'login')
        self.addCleanup(cloud.SESSIONS.pop, sid, None)
        self.assertEqual(request.call_args.args[2]['token'], '12345678')
        self.assertNotIn('12345678', str(result))

    def test_leading_zero_code_stays_six_digits(self):
        with patch.object(smtp_otp.secrets, 'randbelow', return_value=42), \
             patch.object(cloud, 'request', return_value={'email_otp': '87654321'}), \
             patch.object(smtp_otp, 'deliver') as mail:
            cloud.send_code('person@example.com', 'login')
        mail.assert_called_once_with('person@example.com', '000042', 10)

    def test_expired_and_wrong_purpose_codes_rejected(self):
        self.send()
        with self.assertRaises(cloud.CloudError):
            smtp_otp.verify('person@example.com', '123456', 'recovery', cloud.CloudError)
        smtp_otp.PENDING['person@example.com']['expires'] = 0
        with self.assertRaises(cloud.CloudError):
            smtp_otp.verify('person@example.com', '123456', 'login', cloud.CloudError)

    def test_signup_uses_custom_delivery_and_no_session(self):
        with patch.object(cloud, 'request', return_value={'email_otp': '12345678'}) as request, \
             patch.object(smtp_otp, 'deliver'):
            sid, result = cloud.login('person@example.com', 'password123', True, {'full_name':'Person'})
        self.assertIsNone(sid)
        self.assertTrue(result['verification_required'])
        self.assertEqual(request.call_args.args[2]['type'], 'signup')

    def test_mail_failure_does_not_leave_usable_code(self):
        with patch.object(cloud, 'request', return_value={'email_otp': '12345678'}), \
             patch.object(smtp_otp, 'deliver', side_effect=OSError('private server detail')):
            with self.assertRaises(cloud.CloudError) as error:
                cloud.send_code('person@example.com', 'login')
        self.assertNotIn('private', str(error.exception))
        self.assertIsNone(smtp_otp.PENDING['person@example.com']['digest'])

    def test_smtp_uses_tls_and_sends_numeric_code(self):
        connection = Mock()
        connection.__enter__ = Mock(return_value=connection)
        connection.__exit__ = Mock(return_value=False)
        connection.send_message.return_value = {}
        with patch.object(smtp_otp.smtplib, 'SMTP', return_value=connection):
            smtp_otp.deliver('person@example.com', '12345678', 10)
        connection.starttls.assert_called_once()
        connection.login.assert_called_once_with('sender', 'secret')
        body = connection.send_message.call_args.args[0].get_content()
        self.assertIn('12345678', body)
        self.assertNotIn('https://', body)

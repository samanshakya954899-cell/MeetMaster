"""Custom SMTP delivery. Never return OTPs or admin responses to the browser."""
import hashlib
import hmac
import os
import secrets
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

LOCK = threading.RLock()
PENDING = {}
SEND_TIMES = []


def enabled():
    return bool(os.environ.get('EMAIL_HOST'))


def settings():
    port = int(os.environ.get('EMAIL_PORT', '587'))
    tls = os.environ.get('EMAIL_USE_TLS', 'true').lower() in {'true', '1', 'yes'}
    ssl_mode = port == 465 or os.environ.get('EMAIL_USE_SSL', '').lower() in {'true', '1', 'yes'}
    if not ssl_mode and not tls:
        raise ValueError('SMTP requires TLS or SSL.')
    for key in ('EMAIL_HOST', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'DEFAULT_FROM_EMAIL'):
        if not os.environ.get(key):
            raise ValueError('Missing SMTP configuration.')
    return port, tls, ssl_mode


def deliver(email, code, minutes):
    port, tls, ssl_mode = settings()
    message = EmailMessage()
    message['Subject'] = 'Your Meet Master verification code'
    message['From'] = os.environ['DEFAULT_FROM_EMAIL']
    message['To'] = email
    message.set_content(f'Your Meet Master verification code is:\n\n{code}\n\n'
                        f'Enter it in Meet Master within {minutes} minutes.\n'
                        'If you did not request this code, ignore this email.')
    context = ssl.create_default_context()
    if ssl_mode:
        connection = smtplib.SMTP_SSL(os.environ['EMAIL_HOST'], port, timeout=20, context=context)
    else:
        connection = smtplib.SMTP(os.environ['EMAIL_HOST'], port, timeout=20)
    with connection:
        connection.ehlo()
        if not ssl_mode and tls:
            connection.starttls(context=context)
            connection.ehlo()
        connection.login(os.environ['EMAIL_HOST_USER'], os.environ['EMAIL_HOST_PASSWORD'])
        if connection.send_message(message):
            raise smtplib.SMTPException('Recipient rejected.')


def send(email, purpose, request, error_type, password=None, metadata=None):
    email = email.strip().lower()
    if '\r' in email or '\n' in email or email.count('@') != 1:
        raise error_type('Enter a valid email address.', 400)
    try:
        settings()
        minutes = max(1, min(60, int(os.environ.get('OTP_EXPIRY_MINUTES', '10'))))
        cooldown = max(30, int(os.environ.get('OTP_RESEND_SECONDS', '60')))
    except (ValueError, TypeError):
        raise error_type('SMTP configuration is incomplete or invalid.', 503) from None
    now = time.monotonic()
    with LOCK:
        for key, entry in list(PENDING.items()):
            if entry['retain_until'] <= now:
                PENDING.pop(key, None)
        SEND_TIMES[:] = [stamp for stamp in SEND_TIMES if stamp > now - 60]
        old = PENDING.get(email)
        if old and old['resend_at'] > now:
            raise error_type('Please wait before requesting another code.', 429)
        if len(SEND_TIMES) >= 20 or len(PENDING) >= 1000:
            raise error_type('Too many code requests. Try again later.', 429)
        entry = {'resend_at': now + cooldown, 'retain_until': now + max(minutes * 60, cooldown),
                 'expires': now + minutes * 60, 'purpose': purpose, 'attempts': 0, 'digest': None}
        PENDING[email] = entry
        SEND_TIMES.append(now)
    kind = 'signup' if password is not None else ('recovery' if purpose == 'recovery' else 'magiclink')
    payload = {'type': kind, 'email': email}
    if password is not None:
        payload.update(password=password, data=metadata or {})
    # This admin endpoint generates the OTP but sends no Supabase email.
    result = request('/auth/v1/admin/generate_link', 'POST', payload, admin=True)
    provider_code = result.get('email_otp')
    if not isinstance(provider_code, str) or not provider_code.isascii() or not provider_code.isdigit() or not 6 <= len(provider_code) <= 10:
        raise error_type('The authentication provider did not return a valid email code.', 502)
    code = f'{secrets.randbelow(1_000_000):06d}'
    try:
        deliver(email, code, minutes)
    except (OSError, smtplib.SMTPException, ValueError):
        raise error_type('SMTP could not send your code. Check the mail server credentials and sender settings, then retry.', 502) from None
    with LOCK:
        if PENDING.get(email) is entry:
            entry['digest'] = hashlib.sha256(code.encode()).digest()
            entry['provider_code'] = provider_code
    return {'message': 'A verification code has been sent to your email.', 'verification_required': True}


def verify(email, code, purpose, error_type):
    email = email.strip().lower()
    with LOCK:
        entry = PENDING.get(email)
        if not entry or entry['expires'] <= time.monotonic() or not entry['digest'] or entry['attempts'] >= 5:
            raise error_type('Request a new code. This code is unavailable or expired.', 400)
        entry['attempts'] += 1
        if len(code) != 6 or not code.isascii() or not code.isdigit() or entry['purpose'] != purpose or not hmac.compare_digest(entry['digest'], hashlib.sha256(code.encode()).digest()):
            raise error_type('Incorrect verification code.', 400)
        entry['digest'] = None  # One attempt to exchange a correct code; never replay it.
        provider_code = entry.pop('provider_code')
    return email, provider_code

"""Backend Supabase REST storage and server-side Auth sessions."""
from contextvars import ContextVar
from http.cookies import SimpleCookie
import json
import base64
import hashlib
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlencode, urlparse
import urllib.error
import urllib.request
if __package__:
    from . import smtp_otp
else:
    import smtp_otp

CURRENT = ContextVar('supabase_session', default=None)
SESSIONS = {}
LOCK = threading.RLock()
OAUTH = {}
SETTINGS = {'until': 0, 'google': False}


class CloudError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def load_env(path):
    if not Path(path).exists():
        return
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def enabled():
    return os.environ.get('DATABASE_BACKEND', 'sqlite') == 'supabase'


def request(path, method='GET', data=None, access=None, prefer=None, admin=False):
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_PUBLISHABLE_KEY', '')
    if admin:
        if path != '/auth/v1/admin/generate_link' or method != 'POST':
            raise CloudError('Unsupported admin operation.', 400)
        key = os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
        if not key:
            raise CloudError('Set the backend Supabase secret key for SMTP OTP delivery.', 503)
    parsed = urlparse(base)
    if parsed.scheme != 'https' or not (parsed.hostname or '').endswith('.supabase.co') or not key or parsed.path or parsed.username:
        raise CloudError('Supabase URL or publishable key is missing or invalid.', 503)
    headers = {'apikey': key, 'Accept': 'application/json'}
    if admin and not key.startswith('sb_secret_'):
        headers['Authorization'] = 'Bearer ' + key
    if access:
        headers['Authorization'] = 'Bearer ' + access
    if prefer:
        headers['Prefer'] = prefer
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(base + path, method=method,
        data=None if data is None else json.dumps(data).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise CloudError('Supabase response exceeds the supported size.', 502)
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read(4096))
            code = payload.get('error_code') or payload.get('code')
            if not isinstance(code, str):
                code = None
        except (ValueError, AttributeError):
            code = None
        if code in {'PGRST205', 'PGRST202', '42P01'}:
            raise CloudError('Meet Master schema is not installed. Run supabase/schema.sql in the Supabase SQL Editor, then reload.', 503) from None
        if code == '42501':
            raise CloudError('Database permissions are missing. Run the complete schema.sql file including grants and RLS policies.', 403) from None
        if code in {'email_not_confirmed'}:
            raise CloudError('Confirm your email before signing in.', 401) from None
        if code in {'invalid_credentials'}:
            raise CloudError('Email or password is incorrect.', 401) from None
        if code == 'otp_expired':
            raise CloudError('This code is invalid or expired. Request a new code.', 400) from None
        auth_errors = {
            'otp_disabled': 'Email OTP sign-in is disabled in Supabase Auth.',
            'signup_disabled': 'Account creation is disabled. Use an existing account or contact the workspace owner.',
            'signups_not_allowed': 'This OTP flow requires a registered account. Choose Sign up first, then request an email OTP.',
            'email_address_invalid': 'Enter a valid email address.',
            'email_address_not_authorized': 'The email provider cannot deliver to this address. Check the Supabase SMTP sender configuration.',
            'email_provider_disabled': 'Email authentication is disabled in Supabase Auth.',
            'validation_failed': 'Supabase could not validate this request. Check the email and form fields.',
        }
        if code in auth_errors:
            raise CloudError(auth_errors[code], 422) from None
        if code == 'weak_password':
            raise CloudError('Choose a stronger password with at least eight characters.', 400) from None
        if error.code in {401, 403}:
            raise CloudError('Supabase rejected authentication or access. Sign in again.', 401) from None
        if error.code == 429:
            raise CloudError('Too many requests. Wait before trying again.', 429) from None
        if path.startswith('/auth/') and error.code == 422:
            safe_code = code if isinstance(code, str) and len(code) <= 80 and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in code) else 'unknown'
            raise CloudError(f'Authentication request could not be processed (HTTP 422, code: {safe_code}).', 422) from None
        raise CloudError(f'Supabase request failed (HTTP {error.code}). Existing local data is unchanged.', 502) from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise CloudError('Supabase is unavailable. No local fallback was used; try again later.', 502) from None


def login(email, password, signup=False, metadata=None):
    if signup and smtp_otp.enabled():
        return None, smtp_otp.send(email, 'signup', request, CloudError, password, metadata)
    path = '/auth/v1/signup' if signup else '/auth/v1/token?grant_type=password'
    body = {'email': email, 'password': password}
    if signup:
        body['data'] = metadata or {}
    response = request(path, 'POST', body)
    if not response.get('access_token'):
        return None, {'message': 'Check your email for confirmation. Enter the code here if your email includes one.', 'verification_required': True}
    return register_session(response)


def register_session(response, recovery=False):
    session = make_session(response)
    session['recovery'] = recovery
    with LOCK:
        # Bound local memory without exposing session tokens to the browser.
        for ident, old in list(SESSIONS.items()):
            if old['local_expiry'] < time.time():
                SESSIONS.pop(ident, None)
        if len(SESSIONS) >= 200:
            raise CloudError('Too many active local sessions. Restart the server.', 503)
        sid = secrets.token_urlsafe(32)
        SESSIONS[sid] = session
    return sid, {'message': 'Signed in successfully.'}


def send_code(email, purpose):
    if smtp_otp.enabled():
        return smtp_otp.send(email, purpose, request, CloudError)
    if purpose == 'signup':
        request('/auth/v1/resend', 'POST', {'email': email, 'type': 'signup'})
    elif purpose == 'recovery':
        request('/auth/v1/recover', 'POST', {'email': email})
    else:
        request('/auth/v1/otp', 'POST', {'email': email, 'create_user': True})
    return {'message': 'If this email is eligible, a verification email is on its way.'}


def verify_code(email, code, purpose):
    if smtp_otp.enabled():
        email, code = smtp_otp.verify(email, code, purpose, CloudError)
    response = request('/auth/v1/verify', 'POST', {'email': email, 'token': code,
                       'type': 'recovery' if purpose == 'recovery' else 'email'})
    return register_session(response, recovery=purpose == 'recovery')


def change_password(password):
    session = CURRENT.get()
    if not session or not session.get('recovery'):
        raise CloudError('Verify your password reset code first.', 401)
    request('/auth/v1/user', 'PUT', {'password': password}, access=session['access'])
    session['recovery'] = False
    return {'message': 'Password updated. You are signed in.'}


def google_enabled():
    with LOCK:
        if SETTINGS['until'] < time.time():
            try:
                SETTINGS['google'] = bool(request('/auth/v1/settings').get('external', {}).get('google'))
            except CloudError:
                SETTINGS['google'] = False
            SETTINGS['until'] = time.time() + 60
        return SETTINGS['google']


def start_google(redirect):
    if not google_enabled():
        raise CloudError('Google sign-in must be enabled in Supabase Authentication → Providers.', 503)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    with LOCK:
        for ident, flow in list(OAUTH.items()):
            if flow['expires'] < time.time():
                OAUTH.pop(ident, None)
        if len(OAUTH) >= 200:
            raise CloudError('Too many sign-in attempts. Try again later.', 429)
        flow_id = secrets.token_urlsafe(32)
        OAUTH[flow_id] = {'verifier': verifier, 'expires': time.time() + 600}
    url = os.environ['SUPABASE_URL'].rstrip('/') + '/auth/v1/authorize?' + urlencode({
        'provider': 'google', 'redirect_to': redirect, 'code_challenge': challenge, 'code_challenge_method': 's256'})
    return flow_id, {'url': url}


def finish_google(cookie_value, code):
    cookie = SimpleCookie()
    cookie.load(cookie_value or '')
    ident = cookie['mm_oauth'].value if 'mm_oauth' in cookie else None
    with LOCK:
        flow = OAUTH.pop(ident, None)
    if not flow or flow['expires'] < time.time() or not code or len(code) > 2048:
        raise CloudError('Google sign-in expired. Start again.', 401)
    response = request('/auth/v1/token?grant_type=pkce', 'POST', {'auth_code': code, 'code_verifier': flow['verifier']})
    return register_session(response)


def make_session(response):
    user = response.get('user') or {}
    if not user.get('id') or not response.get('access_token') or not response.get('refresh_token'):
        raise CloudError('Supabase returned an invalid authentication response.', 502)
    return {'access': response['access_token'], 'refresh': response['refresh_token'],
            'user': {'id': user['id'], 'email': user.get('email', ''),
                     'name': str((user.get('user_metadata') or {}).get('full_name', 'Meet Master'))[:100],
                     'company': str((user.get('user_metadata') or {}).get('company', ''))[:100]},
            'expires': time.time() + int(response.get('expires_in', 3600)),
            'local_expiry': time.time() + 7 * 86400}


def sid_from_cookie(value):
    cookie = SimpleCookie()
    try:
        cookie.load(value or '')
        return cookie['mm_session'].value if 'mm_session' in cookie else None
    except Exception:
        return None


def bind(cookie):
    CURRENT.set(None)
    sid = sid_from_cookie(cookie)
    with LOCK:
        session = SESSIONS.get(sid)
        if not session:
            return
        if session['local_expiry'] < time.time():
            SESSIONS.pop(sid, None)
            return
        if session['expires'] < time.time() + 30:
            try:
                refreshed = request('/auth/v1/token?grant_type=refresh_token', 'POST', {'refresh_token': session['refresh']})
                session.update(make_session(refreshed))
            except CloudError:
                SESSIONS.pop(sid, None)
                return
        CURRENT.set(session)


def logout(cookie):
    with LOCK:
        SESSIONS.pop(sid_from_cookie(cookie), None)
    CURRENT.set(None)


def store():
    session = CURRENT.get()
    if not session:
        raise CloudError('Sign in to your Supabase account first.', 401)
    return Store(session)


class Store:
    def __init__(self, session):
        self.access = session['access']
        self.owner = session['user']['id']

    def call(self, table, method='GET', data=None, filters=None, prefer=None):
        path = '/rest/v1/' + table
        if filters:
            path += '?' + urlencode(filters)
        return request(path, method, data, self.access, prefer)

    def listing(self, table):
        result = []
        for offset in range(0, 10000, 1000):
            batch = self.call(table, filters={'owner_id': 'eq.' + self.owner,
                'order': 'created.desc,id.asc', 'limit': '1000', 'offset': str(offset)})
            result.extend(batch)
            if len(batch) < 1000:
                return result
        raise CloudError('Workspace exceeds 10,000 records. Add paginated views before loading more.', 413)

    def one(self, table, ident):
        rows = self.call(table, filters={'id': 'eq.' + ident, 'owner_id': 'eq.' + self.owner, 'limit': '1'})
        if not rows:
            raise CloudError('Record not found in your workspace.', 404)
        return rows[0]

    def save(self, table, value, update=False):
        payload = dict(value)
        payload['owner_id'] = self.owner
        if update:
            # RLS and owner filter both scope writes to the signed-in user.
            rows = self.call(table, 'PATCH', payload,
                {'id': 'eq.' + value['id'], 'owner_id': 'eq.' + self.owner}, 'return=representation')
            if not rows:
                raise CloudError('Record not found in your workspace.', 404)
            return rows[0]
        return self.call(table, 'POST', payload, prefer='return=representation')[0]

    def update_meeting(self, ident, fields):
        return self.save('mm_meetings', {'id': ident, **fields}, update=True)

    def profile(self):
        rows = self.call('mm_profiles', filters={'user_id': 'eq.' + self.owner, 'limit': '1'})
        return {'name': rows[0]['name'], 'company': rows[0]['company']} if rows else None

    def save_profile(self, profile):
        self.call('mm_profiles', 'POST', {'user_id': self.owner, **profile},
                  {'on_conflict': 'user_id'}, 'resolution=merge-duplicates,return=minimal')

    def delete_agent(self, ident):
        self.call('rpc/mm_delete_agent', 'POST', {'p_id': ident})

    def import_local(self, payload):
        return self.call('rpc/mm_import_workspace', 'POST', {'p_data': payload})

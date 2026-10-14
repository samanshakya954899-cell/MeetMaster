# Meet Master email codes and Google sign-in

The app now supports email-first password login, signup with profile metadata,
email-code login, signup verification, and password recovery. Sessions stay on
the Python server in HttpOnly cookies; passwords and provider tokens are not
saved in browser storage. Restarting the Python server requires signing in again.

## Enable code emails

In Supabase → Authentication → Email Templates, update **Confirm signup**,
**Magic Link**, and **Reset Password** so each email includes `{{ .Token }}`.
For example, use this email body, adapting the heading for each template:

```html
<h2>Your Meet Master verification code</h2>
<p>Enter this code in Meet Master:</p>
<p style="font-size:28px;font-weight:bold;letter-spacing:6px">{{ .Token }}</p>
<p>If you did not request this email, you can ignore it.</p>
```

Keep email confirmations enabled for signup verification. Supabase may send
links instead of numeric codes until these templates are changed. Password
recovery verifies a recovery code before showing the new-password form.
Email delivery and rate limits depend on your Supabase email/SMTP configuration.
Requesting a login code creates an account for a new email address. The user
must verify the emailed OTP before the app creates a signed-in session.

Official guide: [Supabase email OTP](https://supabase.com/docs/guides/auth/auth-email-passwordless).

## Enable Google

In Supabase → Authentication → Sign In / Providers → Google, configure your
Google OAuth client and enable the provider. Use the Supabase callback URL
displayed there as a Google authorized redirect URI.

In Supabase → Authentication → URL Configuration, allow this app callback:

```text
http://127.0.0.1:8787/api/auth/callback
```

If using localhost instead of 127.0.0.1, also allow:

```text
http://localhost:8787/api/auth/callback
```

Refresh the app after enabling the provider (status is cached for 60 seconds).
The Google button is disabled while the provider is unavailable. Google login
uses a server-held PKCE verifier and a one-time OAuth cookie; it does not show
a fabricated Google account chooser or preselected user.

Official guide: [Supabase Google login](https://supabase.com/docs/guides/auth/social-login/auth-google).

The database tables still require running `supabase/schema.sql` in the project's
SQL Editor. Authentication and schema setup are separate steps.

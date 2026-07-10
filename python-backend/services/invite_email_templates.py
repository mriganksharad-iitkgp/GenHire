"""HTML/text templates for invite emails.

Each render function returns a (subject, html, text) tuple. We use inline
styles on every important element so that mail clients which strip <style>
blocks (Gmail, Outlook, Apple Mail in some configs) still render correctly.
"""

from datetime import datetime
from html import escape


# -- Shared style fragments ----------------------------------------------------

PRIMARY = "#4F46E5"
PRIMARY_DARK = "#3730A3"
TEXT = "#111827"
MUTED = "#6B7280"
BORDER = "#E5E7EB"
SOFT_BG = "#F9FAFB"
ACCENT_BG = "#EEF2FF"

BTN_STYLE = (
    "display:inline-block;"
    "padding:14px 36px;"
    f"background-color:{PRIMARY};"
    "color:#ffffff !important;"
    "text-decoration:none !important;"
    "font-weight:700;"
    "font-size:16px;"
    "font-family:Arial,Helvetica,sans-serif;"
    "border-radius:8px;"
    "letter-spacing:0.2px;"
    "mso-padding-alt:14px 36px;"
    "-webkit-text-size-adjust:none;"
    "border:1px solid " + PRIMARY + ";"
)

CONTAINER_STYLE = (
    "max-width:600px;"
    "margin:0 auto;"
    "background:#ffffff;"
    "border-radius:12px;"
    "overflow:hidden;"
    "box-shadow:0 6px 24px rgba(15,23,42,0.08);"
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
)

HEADER_STYLE = (
    f"background:linear-gradient(135deg,{PRIMARY} 0%,{PRIMARY_DARK} 100%);"
    "color:#ffffff;"
    "padding:32px 28px;"
    "text-align:center;"
)

CONTENT_STYLE = (
    "padding:32px 28px;"
    f"color:{TEXT};"
    "font-size:15px;"
    "line-height:1.65;"
)

FOOTER_STYLE = (
    "padding:18px 28px;"
    f"background:{SOFT_BG};"
    f"border-top:1px solid {BORDER};"
    f"color:{MUTED};"
    "font-size:12px;"
    "text-align:center;"
)

CRED_BOX_STYLE = (
    f"background:{ACCENT_BG};"
    f"border-left:4px solid {PRIMARY};"
    "padding:14px 18px;"
    "border-radius:6px;"
    "margin:20px 0;"
    "font-size:14px;"
    f"color:{TEXT};"
)

NOTE_STYLE = (
    f"color:{MUTED};"
    "font-size:13px;"
    "line-height:1.55;"
    "margin-top:14px;"
)

LINK_FALLBACK_STYLE = (
    f"color:{PRIMARY};"
    "word-break:break-all;"
    "font-size:13px;"
    "margin:8px 0 0 0;"
)


def _humanize_validity(valid_until, validity_days) -> str:
    """'7 days (until 18 Jul 2026)' — recruiter-chosen access window that both
    the magic link and the Invite ID + password login honour."""
    parts = []
    if validity_days:
        parts.append(f"{int(validity_days)} day{'s' if int(validity_days) != 1 else ''}")
    if valid_until is not None:
        try:
            parts.append(f"until {valid_until.strftime('%d %b %Y')} (UTC)")
        except AttributeError:
            parts.append(f"until {valid_until}")
    return " — ".join(parts) if parts else "a limited time"


def _shell(header_eyebrow: str, header_title: str, body_html: str) -> str:
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(header_title)}</title>
</head>
<body style="margin:0;padding:24px 12px;background-color:#F3F4F6;">
  <div style="{CONTAINER_STYLE}">
    <div style="{HEADER_STYLE}">
      <div style="font-size:12px;letter-spacing:1.5px;text-transform:uppercase;opacity:0.85;margin-bottom:6px;">{escape(header_eyebrow)}</div>
      <h1 style="margin:0;font-size:24px;font-weight:700;line-height:1.3;">{escape(header_title)}</h1>
    </div>
    <div style="{CONTENT_STYLE}">
      {body_html}
    </div>
    <div style="{FOOTER_STYLE}">
      &copy; {year} GenHire &middot; You received this email because someone invited you to a role on GenHire.
    </div>
  </div>
</body>
</html>"""


def _button(href: str, label: str) -> str:
    """A bulletproof CTA button. White text is enforced at five layers:
    (1) anchor inline style with !important, (2) <font color> attr,
    (3) <font style="color">, (4) <span style="color">, and (5) inline
    color on the label text itself. Gmail / Outlook / Dark Mode each pick
    a different layer, so we cover all of them."""
    safe_href = escape(href)
    safe_label = escape(label)
    return (
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" '
        f'style="margin:24px auto;"><tr><td align="center" bgcolor="{PRIMARY}" '
        f'style="border-radius:8px; background-color:{PRIMARY}; mso-padding-alt:0;">'
        f'<a href="{safe_href}" target="_blank" '
        f'style="{BTN_STYLE}">'
        f'<font color="#ffffff" face="Arial, Helvetica, sans-serif" '
        f'style="color:#ffffff !important; text-decoration:none !important;">'
        f'<span style="color:#ffffff !important; text-decoration:none !important; '
        f'font-weight:700; font-size:16px; font-family:Arial,Helvetica,sans-serif;">'
        f'{safe_label}'
        f'</span>'
        f'</font>'
        f'</a>'
        f"</td></tr></table>"
    )


# -- Public renderers ----------------------------------------------------------


def render_apply_invite(
    *,
    recruiter_company: str,
    job_title: str,
    magic_link: str,
    invite_id: str,
    temp_password: str,
    valid_until=None,
    validity_days=None,
    **_kwargs,
):
    company = escape(recruiter_company or "A hiring team")
    title = escape(job_title or "an open role")
    validity = _humanize_validity(valid_until, validity_days)

    subject = f"{recruiter_company or 'GenHire'} would love your application for {job_title}"

    body_html = f"""
        <p style="margin:0 0 14px 0;">Hi there,</p>
        <p style="margin:0 0 14px 0;"><strong>{company}</strong> is hiring for <strong>{title}</strong> and thinks you might be a great fit. We've set up a quick way for you to apply on GenHire without having to register from scratch.</p>
        <p style="margin:0 0 6px 0;">Click below to sign in &mdash; no signup, no password reset:</p>
        {_button(magic_link, "View Job")}
        <p style="margin:0;color:{MUTED};font-size:13px;">Or paste this link into your browser:</p>
        <p style="{LINK_FALLBACK_STYLE}"><a href="{escape(magic_link)}" style="color:{PRIMARY};">{escape(magic_link)}</a></p>
        <div style="{CRED_BOX_STYLE}">
            <div><strong>Your Invite ID:</strong> <span style="font-family:Consolas,'Courier New',monospace;">{escape(invite_id)}</span></div>
            <div style="margin-top:6px;"><strong>Password:</strong> <span style="font-family:Consolas,'Courier New',monospace;">{escape(temp_password)}</span></div>
            <div style="font-size:13px;color:{MUTED};margin-top:8px;">You can also sign in directly at the login page with these credentials. The Invite ID is unique to this invitation, so the same email can hold multiple Invite IDs.</div>
        </div>
        <p style="{NOTE_STYLE}">This invite &mdash; both the magic link and the Invite ID + password login &mdash; is valid for <strong>{escape(validity)}</strong>. After that, ask the hiring team to re-send your invite.</p>
        <p style="{NOTE_STYLE}">If you weren't expecting this email, you can safely ignore it.</p>
    """
    html = _shell("You're invited to apply", f"Apply for {job_title or 'this role'}", body_html)

    text = f"""
Hi there,

{recruiter_company or 'A hiring team'} is hiring for {job_title or 'an open role'} and thinks you might be a great fit.

Click below to sign in -- no signup, no password reset:
{magic_link}

Your sign-in credentials:
  Invite ID: {invite_id}
  Password:  {temp_password}

This invite -- both the magic link and the Invite ID + password login -- is valid for {validity}. After that, ask the hiring team to re-send your invite.

If you weren't expecting this email, you can safely ignore it.

(c) {datetime.now().year} GenHire. All rights reserved.
""".strip()

    return subject, html, text


def render_interview_invite(
    *,
    recruiter_company: str,
    job_title: str,
    magic_link: str,
    invite_id: str,
    temp_password: str,
    valid_until=None,
    validity_days=None,
    **_kwargs,
):
    company = escape(recruiter_company or "A hiring team")
    title = escape(job_title or "an open role")
    validity = _humanize_validity(valid_until, validity_days)

    subject = f"You're pre-shortlisted for {job_title} at {recruiter_company or 'GenHire'}"

    body_html = f"""
        <p style="margin:0 0 14px 0;">Hi there,</p>
        <p style="margin:0 0 14px 0;">Great news &mdash; <strong>{company}</strong> has pre-shortlisted you for an interview for <strong>{title}</strong>. Once you upload your CV you'll be ready to start the interview &mdash; no waiting on a separate review step.</p>
        <p style="margin:0 0 6px 0;">Click below to sign in &mdash; no signup, no password reset:</p>
        {_button(magic_link, "View Job")}
        <p style="margin:0;color:{MUTED};font-size:13px;">Or paste this link into your browser:</p>
        <p style="{LINK_FALLBACK_STYLE}"><a href="{escape(magic_link)}" style="color:{PRIMARY};">{escape(magic_link)}</a></p>
        <div style="{CRED_BOX_STYLE}">
            <div><strong>Your Invite ID:</strong> <span style="font-family:Consolas,'Courier New',monospace;">{escape(invite_id)}</span></div>
            <div style="margin-top:6px;"><strong>Password:</strong> <span style="font-family:Consolas,'Courier New',monospace;">{escape(temp_password)}</span></div>
            <div style="font-size:13px;color:{MUTED};margin-top:8px;">You can also sign in directly at the login page with these credentials. The Invite ID is unique to this invitation, so the same email can hold multiple Invite IDs.</div>
        </div>
        <p style="{NOTE_STYLE}">This invite &mdash; both the magic link and the Invite ID + password login &mdash; is valid for <strong>{escape(validity)}</strong>. After that, ask the hiring team to re-send your invite.</p>
        <p style="{NOTE_STYLE}">If you weren't expecting this email, you can safely ignore it.</p>
    """
    html = _shell("You're invited to interview", f"Interview for {job_title or 'this role'}", body_html)

    text = f"""
Hi there,

{recruiter_company or 'A hiring team'} has pre-shortlisted you for an interview for {job_title or 'an open role'}. Once you upload your CV you'll be ready to start the interview -- no waiting on a separate review step.

Click below to sign in -- no signup, no password reset:
{magic_link}

Your sign-in credentials:
  Invite ID: {invite_id}
  Password:  {temp_password}

This invite -- both the magic link and the Invite ID + password login -- is valid for {validity}. After that, ask the hiring team to re-send your invite.

If you weren't expecting this email, you can safely ignore it.

(c) {datetime.now().year} GenHire. All rights reserved.
""".strip()

    return subject, html, text

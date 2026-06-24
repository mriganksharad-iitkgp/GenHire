import os
from textwrap import dedent
from datetime import datetime
from html import escape
from typing import Optional

from services.email_providers import get_email_provider
from services.invite_email_templates import (
    render_apply_invite,
    render_existing_user_invite,
    render_interview_invite,
)


class EmailService:
    def __init__(self):
        self.provider = get_email_provider()
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")

    def send_email(self, to_email, subject, html_content, text_content=None):
        """Send an email via the configured provider."""
        return bool(self.provider.send(to_email, subject, html_content, text_content))

    def _render_auth_email(
        self,
        *,
        title: str,
        eyebrow: str,
        greeting_name: str,
        intro: str,
        cta_label: str,
        action_url: str,
        expiry_text: str,
        notice_title: str,
        notice_body: str,
    ) -> str:
        safe_name = escape(greeting_name or "there")
        safe_title = escape(title)
        safe_eyebrow = escape(eyebrow)
        safe_intro = escape(intro)
        safe_cta_label = escape(cta_label)
        action_url = str(action_url or "").strip()
        if not action_url.startswith(("http://", "https://")):
            raise ValueError("Email action URL must be an absolute HTTP(S) URL")

        safe_action_url = escape(action_url, quote=True)
        safe_expiry_text = escape(expiry_text)
        safe_notice_title = escape(notice_title)
        safe_notice_body = escape(notice_body)
        year = datetime.now().year

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{safe_title}</title>
        </head>
        <body style="margin:0; padding:0; background:#f4f7fb; font-family:Arial, Helvetica, sans-serif; color:#172033;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f7fb; margin:0; padding:32px 12px;">
                <tr>
                    <td align="center">
                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:640px; background:#ffffff; border:1px solid #e6ebf5; border-radius:14px; overflow:hidden; box-shadow:0 16px 36px rgba(15, 23, 42, 0.08);">
                            <tr>
                                <td style="padding:22px 40px; background:#ffffff; border-bottom:1px solid #edf1f7;">
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                        <tr>
                                            <td style="width:38px; height:38px; background:#5b46f6; border-radius:10px; color:#ffffff; font-size:22px; line-height:38px; font-weight:700; text-align:center;">G</td>
                                            <td style="padding-left:12px; color:#111827; font-size:24px; line-height:30px; font-weight:700;">Genhire</td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            <tr>
                                <td style="background:#091831; padding:42px 40px;">
                                    <div style="color:#9fb3d9; font-size:13px; line-height:18px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; margin:0 0 12px 0;">{safe_eyebrow}</div>
                                    <h1 style="color:#ffffff; font-size:30px; line-height:38px; font-weight:800; margin:0;">{safe_title}</h1>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding:34px 40px 38px 40px;">
                                    <p style="font-size:15px; line-height:24px; margin:0 0 16px 0; color:#2d3748;">Hi {safe_name},</p>
                                    <p style="font-size:15px; line-height:24px; margin:0 0 24px 0; color:#2d3748;">{safe_intro}</p>
                                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="border-collapse:separate; border-spacing:0; margin:0 auto 28px auto;">
                                        <tr>
                                            <td align="center" bgcolor="#5b46f6" style="background:#5b46f6; border-radius:8px; mso-padding-alt:14px 34px;">
                                                <a href="{safe_action_url}" target="_blank" rel="noopener noreferrer" role="button" aria-label="{safe_cta_label}" title="{safe_cta_label}" style="background:#5b46f6; border:1px solid #5b46f6; border-radius:8px; color:#ffffff; cursor:pointer; display:block; font-family:Arial, Helvetica, sans-serif; font-size:15px; font-weight:700; line-height:20px; mso-padding-alt:0; padding:14px 34px; text-align:center; text-decoration:none; white-space:nowrap;">
                                                    <span style="color:#ffffff; cursor:pointer; text-decoration:none;">{safe_cta_label}</span>
                                                </a>
                                            </td>
                                        </tr>
                                    </table>
                                    <div style="height:1px; background:#e8edf6; margin:0 0 22px 0;"></div>
                                    <p style="font-size:13px; line-height:20px; margin:0 0 8px 0; color:#64748b;">Or copy and paste this link into your browser:</p>
                                    <p style="font-size:13px; line-height:20px; margin:0 0 18px 0; word-break:break-all;"><a href="{safe_action_url}" style="color:#4f46e5; text-decoration:underline;">{safe_action_url}</a></p>
                                    <p style="font-size:14px; line-height:22px; margin:0 0 22px 0; color:#475569;">{safe_expiry_text}</p>
                                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f0ff; border-radius:10px; border-left:4px solid #5b46f6;">
                                        <tr>
                                            <td style="padding:16px 18px;">
                                                <p style="font-size:14px; line-height:22px; margin:0; color:#342b7a;"><strong>{safe_notice_title}</strong> {safe_notice_body}</p>
                                            </td>
                                        </tr>
                                    </table>
                                </td>
                            </tr>
                            <tr>
                                <td align="center" style="padding:20px 40px; background:#f8fafc; color:#7a8699; font-size:12px; line-height:18px;">
                                    &copy; {year} Genhire. All rights reserved.
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """

    def send_verification_email(self, to_email, verification_token, user_name):
        """Send email verification link."""
        verification_link = f"{self.frontend_url}/verify-email?token={verification_token}"
        subject = "Verify your Genhire account"

        html_content = self._render_auth_email(
            title="Verify your email address",
            eyebrow="Account verification",
            greeting_name=user_name,
            intro="Thanks for creating a Genhire account. Confirm your email address to activate your account and keep your hiring profile secure.",
            cta_label="Verify Email Address",
            action_url=verification_link,
            expiry_text="This verification link will expire in 24 hours.",
            notice_title="Security Notice:",
            notice_body="If you did not create a Genhire account, you can safely ignore this email.",
        )

        text_content = dedent(f"""
        Hi {user_name},

        Thanks for creating a Genhire account. Please verify your email address to activate your account.

        Click this link to verify your email: {verification_link}

        This link will expire in 24 hours.

        If you didn't create a Genhire account, you can safely ignore this email.

        (c) {datetime.now().year} Genhire. All rights reserved.
        """).strip()

        return self.send_email(to_email, subject, html_content, text_content)

    def send_password_reset_email(self, to_email, reset_token, user_name):
        """Send password reset link."""
        reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
        subject = "Reset your Genhire password"

        html_content = self._render_auth_email(
            title="Password reset request",
            eyebrow="Account security",
            greeting_name=user_name,
            intro="We received a request to reset the password for your Genhire account. Use the secure button below to choose a new password.",
            cta_label="Reset Password",
            action_url=reset_link,
            expiry_text="This password reset link will expire in 1 hour for security reasons.",
            notice_title="Security Notice:",
            notice_body="If you did not request a password reset, please ignore this email. Your password will remain unchanged.",
        )

        text_content = dedent(f"""
        Hi {user_name},

        We received a request to reset your password for your Genhire account.

        Click this link to reset your password: {reset_link}

        This link will expire in 1 hour for security reasons.

        If you didn't request a password reset, please ignore this email. Your password will remain unchanged.

        (c) {datetime.now().year} Genhire. All rights reserved.
        """).strip()

        return self.send_email(to_email, subject, html_content, text_content)

    def send_password_changed_confirmation(self, to_email, user_name):
        """Send confirmation email after successful password change."""
        subject = "Your Genhire password has been changed"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #10B981; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
                .warning {{ background-color: #FEE2E2; padding: 10px; border-left: 4px solid #EF4444; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Changed Successfully</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>This is a confirmation that your Genhire account password has been changed successfully.</p>
                    <p>If you made this change, no further action is required.</p>
                    <div class="warning">
                        <strong>Didn't change your password?</strong><br>
                        If you didn't make this change, please contact our support team immediately and secure your account.
                    </div>
                </div>
                <div class="footer">
                    <p>&copy; {datetime.now().year} Genhire. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
        Hi {user_name},

        This is a confirmation that your Genhire account password has been changed successfully.

        If you made this change, no further action is required.

        If you didn't make this change, please contact our support team immediately and secure your account.

        (c) {datetime.now().year} Genhire. All rights reserved.
        """

        return self.send_email(to_email, subject, html_content, text_content)

    # --- Invite system emails ----------------------------------------------

    def _invite_redeem_link(self, raw_token: str) -> str:
        return f"{self.frontend_url}/invite/redeem?token={raw_token}"

    def _job_link(self, job_id: str) -> str:
        return f"{self.frontend_url}/job/{job_id}"

    def _login_link(self, next_path: Optional[str] = None) -> str:
        if next_path:
            return f"{self.frontend_url}/login?next={next_path}"
        return f"{self.frontend_url}/login"

    def send_invite_apply_email(
        self,
        to_email: str,
        recruiter_company: str,
        job_title: str,
        invite_id: str,
        temp_password: str,
        raw_token: str,
        ttl_minutes: int,
    ) -> bool:
        magic_link = self._invite_redeem_link(raw_token)
        subject, html, text = render_apply_invite(
            recruiter_company=recruiter_company,
            job_title=job_title,
            magic_link=magic_link,
            invite_id=invite_id,
            temp_password=temp_password,
            ttl_minutes=ttl_minutes,
        )
        return self.send_email(to_email, subject, html, text)

    def send_invite_interview_email(
        self,
        to_email: str,
        recruiter_company: str,
        job_title: str,
        invite_id: str,
        temp_password: str,
        raw_token: str,
        ttl_minutes: int,
    ) -> bool:
        magic_link = self._invite_redeem_link(raw_token)
        subject, html, text = render_interview_invite(
            recruiter_company=recruiter_company,
            job_title=job_title,
            magic_link=magic_link,
            invite_id=invite_id,
            temp_password=temp_password,
            ttl_minutes=ttl_minutes,
        )
        return self.send_email(to_email, subject, html, text)

    def send_existing_user_invite_email(
        self,
        to_email: str,
        recruiter_company: str,
        job_title: str,
        job_id: str,
        invite_type: str,
    ) -> bool:
        job_link = self._job_link(job_id)
        subject, html, text = render_existing_user_invite(
            recruiter_company=recruiter_company,
            job_title=job_title,
            job_link=job_link,
            invite_type=invite_type,
        )
        return self.send_email(to_email, subject, html, text)

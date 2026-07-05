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

        html_content = self._render_auth_email(
            title="Password changed successfully",
            eyebrow="Account security",
            greeting_name=user_name,
            intro="This is a confirmation that your Genhire account password was changed successfully. If you made this change, no further action is required.",
            cta_label="Log in to Your Account",
            action_url=f"{self.frontend_url}/login",
            expiry_text="This notification was sent because your password was recently changed.",
            notice_title="Didn't change your password?",
            notice_body="If you did not make this change, please reset your password immediately and contact our support team to secure your account.",
        )

        text_content = dedent(f"""
        Hi {user_name},

        This is a confirmation that your Genhire account password was changed successfully.

        If you made this change, no further action is required.

        If you did not make this change, please reset your password immediately:
        {self.frontend_url}/forgot-password

        (c) {datetime.now().year} Genhire. All rights reserved.
        """).strip()

        return self.send_email(to_email, subject, html_content, text_content)

    def send_interview_complete_notification(
        self,
        to_email: str,
        recruiter_name: str,
        candidate_name: str,
        job_title: str,
        interview_score: Optional[int],
        application_id: str,
    ) -> bool:
        """Notify recruiter when a candidate finishes a real interview."""
        dashboard_url = f"{self.frontend_url}/recruiter-dashboard"
        safe_recruiter = escape(recruiter_name or "there")
        safe_candidate = escape(candidate_name or "A candidate")
        safe_job = escape(job_title or "the position")
        safe_dashboard = escape(dashboard_url, quote=True)
        year = datetime.now().year

        if interview_score is not None:
            score_html = (
                f'<div style="text-align:center; margin:24px 0;">'
                f'<div style="display:inline-block; background:#f0fdf4; border:2px solid #86efac; '
                f'border-radius:14px; padding:16px 32px;">'
                f'<div style="font-size:13px; font-weight:700; color:#166534; '
                f'text-transform:uppercase; letter-spacing:0.06em; margin-bottom:6px;">Interview Score</div>'
                f'<div style="font-size:42px; font-weight:800; color:#15803d; line-height:1;">{interview_score}%</div>'
                f'</div></div>'
            )
            score_text = f"Interview score: {interview_score}%"
        else:
            score_html = ""
            score_text = "Interview score: not yet computed"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Interview completed — {safe_candidate}</title>
</head>
<body style="margin:0;padding:0;background:#f4f7fb;font-family:Arial,Helvetica,sans-serif;color:#172033;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f7fb;margin:0;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:640px;background:#ffffff;border:1px solid #e6ebf5;border-radius:14px;overflow:hidden;box-shadow:0 16px 36px rgba(15,23,42,0.08);">
        <tr>
          <td style="padding:22px 40px;background:#ffffff;border-bottom:1px solid #edf1f7;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>
              <td style="width:38px;height:38px;background:#5b46f6;border-radius:10px;color:#ffffff;font-size:22px;line-height:38px;font-weight:700;text-align:center;">G</td>
              <td style="padding-left:12px;color:#111827;font-size:24px;line-height:30px;font-weight:700;">Genhire</td>
            </tr></table>
          </td>
        </tr>
        <tr>
          <td style="background:#091831;padding:42px 40px;">
            <div style="color:#9fb3d9;font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin:0 0 12px 0;">Interview completed</div>
            <h1 style="color:#ffffff;font-size:28px;line-height:36px;font-weight:800;margin:0;">
              {safe_candidate} finished their interview
            </h1>
          </td>
        </tr>
        <tr>
          <td style="padding:34px 40px 38px 40px;">
            <p style="font-size:15px;line-height:24px;margin:0 0 8px 0;color:#2d3748;">Hi {safe_recruiter},</p>
            <p style="font-size:15px;line-height:24px;margin:0 0 20px 0;color:#2d3748;">
              <strong>{safe_candidate}</strong> has completed their AI interview for <strong>{safe_job}</strong>.
              Their report, transcript, and gaze analysis are ready for your review.
            </p>
            {score_html}
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="border-collapse:separate;margin:0 auto 28px auto;">
              <tr>
                <td align="center" bgcolor="#5b46f6" style="background:#5b46f6;border-radius:8px;">
                  <a href="{safe_dashboard}" target="_blank" rel="noopener noreferrer"
                     style="background:#5b46f6;border:1px solid #5b46f6;border-radius:8px;color:#ffffff;cursor:pointer;display:block;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;line-height:20px;padding:14px 34px;text-align:center;text-decoration:none;white-space:nowrap;">
                    View Interview Report
                  </a>
                </td>
              </tr>
            </table>
            <div style="height:1px;background:#e8edf6;margin:0 0 22px 0;"></div>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f0ff;border-radius:10px;border-left:4px solid #5b46f6;">
              <tr><td style="padding:16px 18px;">
                <p style="font-size:14px;line-height:22px;margin:0;color:#342b7a;">
                  <strong>Next step:</strong> Log in to your recruiter dashboard to review the full report, read the transcript, and check gaze analysis before making a hiring decision.
                </p>
              </td></tr>
            </table>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding:20px 40px;background:#f8fafc;color:#7a8699;font-size:12px;line-height:18px;">
            &copy; {year} Genhire. All rights reserved.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

        text_content = dedent(f"""
        Hi {recruiter_name},

        {candidate_name} has completed their AI interview for {job_title}.
        {score_text}

        Log in to your recruiter dashboard to review the full report, transcript, and gaze analysis:
        {dashboard_url}

        (c) {year} Genhire. All rights reserved.
        """).strip()

        subject = f"Interview complete: {candidate_name} — {job_title}"
        return self.send_email(to_email, subject, html_content, text_content)

    def send_application_status_notification(
        self,
        to_email: str,
        candidate_name: str,
        job_title: str,
        company_name: str,
        new_status: str,
    ) -> bool:
        """Notify candidate when a recruiter changes their application status."""
        dashboard_url = f"{self.frontend_url}/dashboard"
        year = datetime.now().year

        # Canonical status is "screening_cleared"; "selected" is its legacy name.
        if new_status == "selected":
            new_status = "screening_cleared"

        _STATUS_CONFIG = {
            "screening_cleared": {
                "subject": f"Congratulations! You've cleared the screening round — {job_title}",
                "eyebrow": "Application update",
                "title": "Screening cleared!",
                "intro": (
                    f"Congratulations! {escape(company_name or 'The recruiter')} has reviewed your application "
                    f"for <strong>{escape(job_title)}</strong> and you have cleared the AI screening round. "
                    f"The recruiter will contact you directly about the next rounds of their hiring process."
                ),
                "cta_label": "View My Dashboard",
                "expiry_text": "Log in to your Genhire dashboard to see the full update and any further instructions from the recruiter.",
                "notice_title": "What's next?",
                "notice_body": "Check your dashboard and respond promptly to any messages from the recruiter about their further interview rounds.",
            },
            "shortlisted": {
                "subject": f"You've been shortlisted — {job_title}",
                "eyebrow": "Application update",
                "title": "You've been shortlisted",
                "intro": (
                    f"Good news! {escape(company_name or 'The recruiter')} has shortlisted your application "
                    f"for <strong>{escape(job_title)}</strong>. You may be contacted soon for the next stage."
                ),
                "cta_label": "View My Dashboard",
                "expiry_text": "Log in to your Genhire dashboard to see the full update.",
                "notice_title": "Stay prepared:",
                "notice_body": "Keep your profile and CV up to date. The recruiter may reach out with next steps soon.",
            },
            "rejected": {
                "subject": f"Application update — {job_title}",
                "eyebrow": "Application update",
                "title": "Application not progressed",
                "intro": (
                    f"Thank you for applying to <strong>{escape(job_title)}</strong> "
                    f"at {escape(company_name or 'the company')}. After careful review, the recruiter has decided "
                    f"not to move forward with your application at this time."
                ),
                "cta_label": "Browse More Jobs",
                "expiry_text": "Don't be discouraged — there are many more opportunities on Genhire.",
                "notice_title": "Keep practising:",
                "notice_body": "Use Genhire's Practice Mode to sharpen your interview skills and improve your chances for your next application.",
            },
        }

        config = _STATUS_CONFIG.get(new_status)
        if not config:
            return False

        # Build intro with raw HTML (already escaped above) by using a small wrapper
        safe_name = escape(candidate_name or "there")
        safe_dashboard = escape(dashboard_url, quote=True)

        # Replace the generic _render_auth_email intro (which escapes again) with
        # a manually assembled body to support the <strong> tags in intro.
        safe_eyebrow = escape(config["eyebrow"])
        safe_title = escape(config["title"])
        safe_cta = escape(config["cta_label"])
        safe_expiry = escape(config["expiry_text"])
        safe_notice_title = escape(config["notice_title"])
        safe_notice_body = escape(config["notice_body"])

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
</head>
<body style="margin:0;padding:0;background:#f4f7fb;font-family:Arial,Helvetica,sans-serif;color:#172033;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f7fb;margin:0;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:640px;background:#ffffff;border:1px solid #e6ebf5;border-radius:14px;overflow:hidden;box-shadow:0 16px 36px rgba(15,23,42,0.08);">
        <tr>
          <td style="padding:22px 40px;background:#ffffff;border-bottom:1px solid #edf1f7;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>
              <td style="width:38px;height:38px;background:#5b46f6;border-radius:10px;color:#ffffff;font-size:22px;line-height:38px;font-weight:700;text-align:center;">G</td>
              <td style="padding-left:12px;color:#111827;font-size:24px;line-height:30px;font-weight:700;">Genhire</td>
            </tr></table>
          </td>
        </tr>
        <tr>
          <td style="background:#091831;padding:42px 40px;">
            <div style="color:#9fb3d9;font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin:0 0 12px 0;">{safe_eyebrow}</div>
            <h1 style="color:#ffffff;font-size:28px;line-height:36px;font-weight:800;margin:0;">{safe_title}</h1>
          </td>
        </tr>
        <tr>
          <td style="padding:34px 40px 38px 40px;">
            <p style="font-size:15px;line-height:24px;margin:0 0 16px 0;color:#2d3748;">Hi {safe_name},</p>
            <p style="font-size:15px;line-height:24px;margin:0 0 24px 0;color:#2d3748;">{config["intro"]}</p>
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="border-collapse:separate;margin:0 auto 28px auto;">
              <tr>
                <td align="center" bgcolor="#5b46f6" style="background:#5b46f6;border-radius:8px;">
                  <a href="{safe_dashboard}" target="_blank" rel="noopener noreferrer"
                     style="background:#5b46f6;border:1px solid #5b46f6;border-radius:8px;color:#ffffff;cursor:pointer;display:block;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;line-height:20px;padding:14px 34px;text-align:center;text-decoration:none;white-space:nowrap;">
                    {safe_cta}
                  </a>
                </td>
              </tr>
            </table>
            <div style="height:1px;background:#e8edf6;margin:0 0 22px 0;"></div>
            <p style="font-size:14px;line-height:22px;margin:0 0 22px 0;color:#475569;">{safe_expiry}</p>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f0ff;border-radius:10px;border-left:4px solid #5b46f6;">
              <tr><td style="padding:16px 18px;">
                <p style="font-size:14px;line-height:22px;margin:0;color:#342b7a;">
                  <strong>{safe_notice_title}</strong> {safe_notice_body}
                </p>
              </td></tr>
            </table>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding:20px 40px;background:#f8fafc;color:#7a8699;font-size:12px;line-height:18px;">
            &copy; {year} Genhire. All rights reserved.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

        plain_intros = {
            "screening_cleared": f"Congratulations! You have cleared the AI screening round for {job_title} at {company_name or 'the company'}. The recruiter will contact you about the next rounds.",
            "shortlisted": f"{company_name or 'The recruiter'} has shortlisted your application for {job_title}. You may be contacted soon.",
            "rejected": f"Thank you for applying to {job_title}. The recruiter has decided not to move forward with your application at this time.",
        }

        text_content = dedent(f"""
        Hi {candidate_name},

        {plain_intros.get(new_status, '')}

        Log in to your Genhire dashboard to see the full update:
        {dashboard_url}

        (c) {year} Genhire. All rights reserved.
        """).strip()

        return self.send_email(to_email, config["subject"], html_content, text_content)

    def send_application_received_email(
        self, to_email: str, candidate_name: str, job_title: str, company_name: str
    ) -> bool:
        """Confirm to a candidate that their application was received."""
        dashboard_url = f"{self.frontend_url}/profile#applications"
        safe_job = escape(job_title or "the position")
        safe_company = escape(company_name or "the company")

        html_content = self._render_auth_email(
            title="Application received",
            eyebrow="Application update",
            greeting_name=candidate_name,
            intro=(
                f"Thanks for applying to <strong>{safe_job}</strong> at {safe_company}. "
                f"We've received your application and your CV is now being reviewed. "
                f"You'll be notified as soon as there's an update."
            ),
            cta_label="View My Applications",
            action_url=dashboard_url,
            expiry_text="CV review is usually completed within a minute or two.",
            notice_title="What's next?",
            notice_body="Keep an eye on your inbox — you'll hear from us once your CV has been reviewed.",
        )

        text_content = dedent(f"""
        Hi {candidate_name},

        Thanks for applying to {job_title or 'the position'} at {company_name or 'the company'}.

        We've received your application and your CV is now being reviewed. You'll be notified as soon as there's an update.

        View your applications: {dashboard_url}

        (c) {datetime.now().year} Genhire. All rights reserved.
        """).strip()

        return self.send_email(to_email, f"Application received — {job_title or 'your application'}", html_content, text_content)

    def send_new_applicant_notification(
        self, to_email: str, recruiter_name: str, candidate_name: str, job_title: str
    ) -> bool:
        """Notify a recruiter that a new candidate applied to their job."""
        dashboard_url = f"{self.frontend_url}/recruiter-dashboard"
        safe_candidate = escape(candidate_name or "A candidate")
        safe_job = escape(job_title or "your job posting")

        html_content = self._render_auth_email(
            title="New applicant",
            eyebrow="Application update",
            greeting_name=recruiter_name,
            intro=(
                f"<strong>{safe_candidate}</strong> just applied to <strong>{safe_job}</strong>. "
                f"Their CV is being scored automatically and will appear in your dashboard shortly."
            ),
            cta_label="View Applicants",
            action_url=dashboard_url,
            expiry_text="CV scoring usually completes within a minute or two.",
            notice_title="Heads up:",
            notice_body="You don't need to do anything yet — we'll let you know once the candidate's status is finalized.",
        )

        text_content = dedent(f"""
        Hi {recruiter_name},

        {candidate_name or 'A candidate'} just applied to {job_title or 'your job posting'}.

        Their CV is being scored automatically and will appear in your dashboard shortly.

        View applicants: {dashboard_url}

        (c) {datetime.now().year} Genhire. All rights reserved.
        """).strip()

        return self.send_email(to_email, f"New applicant: {candidate_name} — {job_title}", html_content, text_content)

    def send_interview_complete_candidate_email(
        self,
        to_email: str,
        candidate_name: str,
        job_title: str,
        interview_score: Optional[int],
    ) -> bool:
        """Notify the candidate that their own interview has finished and been scored."""
        dashboard_url = f"{self.frontend_url}/profile#applications"
        safe_candidate = escape(candidate_name or "there")
        safe_job = escape(job_title or "the position")
        safe_dashboard = escape(dashboard_url, quote=True)
        year = datetime.now().year

        if interview_score is not None:
            score_html = (
                f'<div style="text-align:center; margin:24px 0;">'
                f'<div style="display:inline-block; background:#f0fdf4; border:2px solid #86efac; '
                f'border-radius:14px; padding:16px 32px;">'
                f'<div style="font-size:13px; font-weight:700; color:#166534; '
                f'text-transform:uppercase; letter-spacing:0.06em; margin-bottom:6px;">Your Interview Score</div>'
                f'<div style="font-size:42px; font-weight:800; color:#15803d; line-height:1;">{interview_score}%</div>'
                f'</div></div>'
            )
            score_text = f"Your interview score: {interview_score}%"
        else:
            score_html = ""
            score_text = "Your interview score is still being calculated."

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Interview completed — {safe_job}</title>
</head>
<body style="margin:0;padding:0;background:#f4f7fb;font-family:Arial,Helvetica,sans-serif;color:#172033;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f7fb;margin:0;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:640px;background:#ffffff;border:1px solid #e6ebf5;border-radius:14px;overflow:hidden;box-shadow:0 16px 36px rgba(15,23,42,0.08);">
        <tr>
          <td style="padding:22px 40px;background:#ffffff;border-bottom:1px solid #edf1f7;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>
              <td style="width:38px;height:38px;background:#5b46f6;border-radius:10px;color:#ffffff;font-size:22px;line-height:38px;font-weight:700;text-align:center;">G</td>
              <td style="padding-left:12px;color:#111827;font-size:24px;line-height:30px;font-weight:700;">Genhire</td>
            </tr></table>
          </td>
        </tr>
        <tr>
          <td style="background:#091831;padding:42px 40px;">
            <div style="color:#9fb3d9;font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin:0 0 12px 0;">Interview completed</div>
            <h1 style="color:#ffffff;font-size:28px;line-height:36px;font-weight:800;margin:0;">
              Your interview for {safe_job} is complete
            </h1>
          </td>
        </tr>
        <tr>
          <td style="padding:34px 40px 38px 40px;">
            <p style="font-size:15px;line-height:24px;margin:0 0 8px 0;color:#2d3748;">Hi {safe_candidate},</p>
            <p style="font-size:15px;line-height:24px;margin:0 0 20px 0;color:#2d3748;">
              Thanks for completing your AI interview for <strong>{safe_job}</strong>. Your results are ready to view.
            </p>
            {score_html}
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="border-collapse:separate;margin:0 auto 28px auto;">
              <tr>
                <td align="center" bgcolor="#5b46f6" style="background:#5b46f6;border-radius:8px;">
                  <a href="{safe_dashboard}" target="_blank" rel="noopener noreferrer"
                     style="background:#5b46f6;border:1px solid #5b46f6;border-radius:8px;color:#ffffff;cursor:pointer;display:block;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;line-height:20px;padding:14px 34px;text-align:center;text-decoration:none;white-space:nowrap;">
                    View My Report
                  </a>
                </td>
              </tr>
            </table>
            <div style="height:1px;background:#e8edf6;margin:0 0 22px 0;"></div>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f0ff;border-radius:10px;border-left:4px solid #5b46f6;">
              <tr><td style="padding:16px 18px;">
                <p style="font-size:14px;line-height:22px;margin:0;color:#342b7a;">
                  <strong>What's next?</strong> The recruiter will review your report and be in touch with next steps. You can check your application status any time from your dashboard.
                </p>
              </td></tr>
            </table>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding:20px 40px;background:#f8fafc;color:#7a8699;font-size:12px;line-height:18px;">
            &copy; {year} Genhire. All rights reserved.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

        text_content = dedent(f"""
        Hi {candidate_name},

        Thanks for completing your AI interview for {job_title}.
        {score_text}

        View your report: {dashboard_url}

        (c) {year} Genhire. All rights reserved.
        """).strip()

        subject = f"Your interview is complete — {job_title}"
        return self.send_email(to_email, subject, html_content, text_content)

    def send_recruiter_approved_email(self, to_email: str, recruiter_name: str, company_name: str) -> bool:
        """Notify recruiter that their account has been approved by admin."""
        dashboard_url = f"{self.frontend_url}/recruiter-dashboard"
        safe_company = escape(company_name or "your company")

        html_content = self._render_auth_email(
            title="Your recruiter account is approved!",
            eyebrow="Account verified",
            greeting_name=recruiter_name,
            intro=(
                f"Great news! Your GenHire recruiter account for <strong>{safe_company}</strong> has been "
                f"reviewed and approved by our admin team. You now have full access to post jobs, "
                f"invite candidates, and manage your hiring pipeline."
            ),
            cta_label="Go to My Dashboard",
            action_url=dashboard_url,
            expiry_text="You can log in at any time using your registered email and password.",
            notice_title="What's next?",
            notice_body=(
                "Head to your dashboard to create your first job posting and start finding the right candidates."
            ),
        )

        text_content = dedent(f"""
        Hi {recruiter_name},

        Great news! Your GenHire recruiter account for {company_name or 'your company'} has been approved.

        You now have full access to post jobs, invite candidates, and manage your hiring pipeline.

        Log in to your dashboard to get started:
        {dashboard_url}

        (c) {datetime.now().year} Genhire. All rights reserved.
        """).strip()

        return self.send_email(
            to_email,
            "Your GenHire recruiter account has been approved",
            html_content,
            text_content,
        )

    def send_recruiter_rejected_email(
        self, to_email: str, recruiter_name: str, company_name: str, rejection_reason: str
    ) -> bool:
        """Notify recruiter that their account application was rejected."""
        year = datetime.now().year
        safe_name = escape(recruiter_name or "there")
        safe_company = escape(company_name or "your company")
        safe_reason = escape(rejection_reason or "Your application did not meet our current requirements.")
        register_url = f"{self.frontend_url}/register"
        safe_register_url = escape(register_url, quote=True)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your GenHire recruiter application was not approved</title>
</head>
<body style="margin:0;padding:0;background:#f4f7fb;font-family:Arial,Helvetica,sans-serif;color:#172033;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f7fb;margin:0;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:640px;background:#ffffff;border:1px solid #e6ebf5;border-radius:14px;overflow:hidden;box-shadow:0 16px 36px rgba(15,23,42,0.08);">
        <tr>
          <td style="padding:22px 40px;background:#ffffff;border-bottom:1px solid #edf1f7;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>
              <td style="width:38px;height:38px;background:#5b46f6;border-radius:10px;color:#ffffff;font-size:22px;line-height:38px;font-weight:700;text-align:center;">G</td>
              <td style="padding-left:12px;color:#111827;font-size:24px;line-height:30px;font-weight:700;">Genhire</td>
            </tr></table>
          </td>
        </tr>
        <tr>
          <td style="background:#7f1d1d;padding:42px 40px;">
            <div style="color:#fca5a5;font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;margin:0 0 12px 0;">Account verification</div>
            <h1 style="color:#ffffff;font-size:28px;line-height:36px;font-weight:800;margin:0;">
              Your recruiter application was not approved
            </h1>
          </td>
        </tr>
        <tr>
          <td style="padding:34px 40px 38px 40px;">
            <p style="font-size:15px;line-height:24px;margin:0 0 8px 0;color:#2d3748;">Hi {safe_name},</p>
            <p style="font-size:15px;line-height:24px;margin:0 0 20px 0;color:#2d3748;">
              Thank you for registering as a recruiter on GenHire for <strong>{safe_company}</strong>.
              After reviewing your application, our admin team was unable to approve it at this time.
            </p>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#fff3f3;border-radius:10px;border-left:4px solid #dc2626;margin:0 0 24px 0;">
              <tr><td style="padding:16px 18px;">
                <p style="font-size:14px;line-height:22px;margin:0 0 4px 0;color:#7f1d1d;font-weight:700;">Reason for rejection:</p>
                <p style="font-size:14px;line-height:22px;margin:0;color:#991b1b;">{safe_reason}</p>
              </td></tr>
            </table>
            <p style="font-size:15px;line-height:24px;margin:0 0 20px 0;color:#2d3748;">
              If you believe this decision was made in error, or if you would like to reapply with updated
              information, please delete your current account and register again making sure all details —
              company name, credentials, and contact information — are accurate and complete.
            </p>
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="border-collapse:separate;margin:0 auto 28px auto;">
              <tr>
                <td align="center" bgcolor="#5b46f6" style="background:#5b46f6;border-radius:8px;">
                  <a href="{safe_register_url}" target="_blank" rel="noopener noreferrer"
                     style="background:#5b46f6;border:1px solid #5b46f6;border-radius:8px;color:#ffffff;cursor:pointer;display:block;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;line-height:20px;padding:14px 34px;text-align:center;text-decoration:none;white-space:nowrap;">
                    Register Again
                  </a>
                </td>
              </tr>
            </table>
            <div style="height:1px;background:#e8edf6;margin:0 0 22px 0;"></div>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f0ff;border-radius:10px;border-left:4px solid #5b46f6;">
              <tr><td style="padding:16px 18px;">
                <p style="font-size:14px;line-height:22px;margin:0;color:#342b7a;">
                  <strong>Need help?</strong> Reply to this email or contact our support team and we'll be happy to assist you through the process.
                </p>
              </td></tr>
            </table>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding:20px 40px;background:#f8fafc;color:#7a8699;font-size:12px;line-height:18px;">
            &copy; {year} Genhire. All rights reserved.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

        text_content = dedent(f"""
        Hi {recruiter_name},

        Thank you for registering as a recruiter on GenHire for {company_name or 'your company'}.
        After reviewing your application, our admin team was unable to approve it at this time.

        Reason for rejection:
        {rejection_reason or 'Your application did not meet our current requirements.'}

        If you would like to reapply, please delete your current account and register again with
        accurate and complete information:
        {register_url}

        If you need help or believe this was an error, reply to this email and we'll assist you.

        (c) {year} Genhire. All rights reserved.
        """).strip()

        return self.send_email(
            to_email,
            "Your GenHire recruiter application was not approved",
            html_content,
            text_content,
        )

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

import os
import requests
from datetime import datetime

class EmailService:
    def __init__(self):
        self.mailgun_api_key = os.getenv('MAILGUN_API_KEY')
        self.mailgun_domain = os.getenv('MAILGUN_DOMAIN')
        self.mailgun_api_url = f"https://api.mailgun.net/v3/{self.mailgun_domain}/messages"
        self.from_email = os.getenv('MAILGUN_FROM_EMAIL', f'noreply@{self.mailgun_domain}')
        self.frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
        
    def send_email(self, to_email, subject, html_content, text_content=None):
        """Send an email using Mailgun API"""
        if not self.mailgun_api_key or not self.mailgun_domain:
            print("Warning: Mailgun credentials not configured")
            return False
            
        try:
            data = {
                'from': self.from_email,
                'to': to_email,
                'subject': subject,
                'html': html_content
            }
            
            if text_content:
                data['text'] = text_content
            
            response = requests.post(
                self.mailgun_api_url,
                auth=('api', self.mailgun_api_key),
                data=data
            )
            
            if response.status_code == 200:
                print(f"Email sent successfully to {to_email}")
                return True
            else:
                print(f"Failed to send email: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False
    
    def send_verification_email(self, to_email, verification_token, user_name):
        """Send email verification link"""
        verification_link = f"{self.frontend_url}/verify-email?token={verification_token}"
        
        subject = "Verify Your HR Tech Account"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
                .button {{ display: inline-block; padding: 12px 30px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to HR Tech!</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>Thanks for signing up! Please verify your email address to get started with HR Tech - your comprehensive HR management platform.</p>
                    <p>Click the button below to verify your email:</p>
                    <center>
                        <a href="{verification_link}" class="button">Verify Email Address</a>
                    </center>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #4F46E5;">{verification_link}</p>
                    <p>This link will expire in 24 hours.</p>
                    <p>If you didn't create an account with HR Tech, you can safely ignore this email.</p>
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} HR Tech. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Hi {user_name},

        Thanks for signing up! Please verify your email address to get started with HR Tech.

        Click this link to verify your email: {verification_link}

        This link will expire in 24 hours.

        If you didn't create an account with HR Tech, you can safely ignore this email.

        © {datetime.now().year} HR Tech. All rights reserved.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_password_reset_email(self, to_email, reset_token, user_name):
        """Send password reset link"""
        reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
        
        subject = "Reset Your HR Tech Password"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
                .button {{ display: inline-block; padding: 12px 30px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
                .warning {{ background-color: #FEF3C7; padding: 10px; border-left: 4px solid #F59E0B; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>We received a request to reset your password for your HR Tech account.</p>
                    <p>Click the button below to reset your password:</p>
                    <center>
                        <a href="{reset_link}" class="button">Reset Password</a>
                    </center>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #4F46E5;">{reset_link}</p>
                    <p>This link will expire in 1 hour for security reasons.</p>
                    <div class="warning">
                        <strong>⚠️ Security Notice:</strong> If you didn't request a password reset, please ignore this email. Your password will remain unchanged.
                    </div>
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} HR Tech. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Hi {user_name},

        We received a request to reset your password for your HR Tech account.

        Click this link to reset your password: {reset_link}

        This link will expire in 1 hour for security reasons.

        If you didn't request a password reset, please ignore this email. Your password will remain unchanged.

        © {datetime.now().year} HR Tech. All rights reserved.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)
    
    def send_password_changed_confirmation(self, to_email, user_name):
        """Send confirmation email after successful password change"""
        subject = "Your HR Tech Password Has Been Changed"
        
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
                    <h1>✓ Password Changed Successfully</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>This is a confirmation that your HR Tech account password has been changed successfully.</p>
                    <p>If you made this change, no further action is required.</p>
                    <div class="warning">
                        <strong>⚠️ Didn't change your password?</strong><br>
                        If you didn't make this change, please contact our support team immediately and secure your account.
                    </div>
                </div>
                <div class="footer">
                    <p>© {datetime.now().year} HR Tech. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Hi {user_name},

        This is a confirmation that your HR Tech account password has been changed successfully.

        If you made this change, no further action is required.

        If you didn't make this change, please contact our support team immediately and secure your account.

        © {datetime.now().year} HR Tech. All rights reserved.
        """
        
        return self.send_email(to_email, subject, html_content, text_content)


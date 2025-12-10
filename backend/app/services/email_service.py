"""Email service using SendGrid for transactional emails."""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, EmailStr
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailType(str, Enum):
    """Types of transactional emails."""
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_REMINDER = "interview_reminder"
    INTERVIEW_CANCELLED = "interview_cancelled"
    OFFER_EXTENDED = "offer_extended"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"
    APPLICATION_RECEIVED = "application_received"
    APPLICATION_STATUS_UPDATE = "application_status_update"
    APPLICATION_REJECTED = "application_rejected"
    SLA_AMBER_ALERT = "sla_amber_alert"
    SLA_RED_ALERT = "sla_red_alert"
    HIRING_MANAGER_REMINDER = "hiring_manager_reminder"
    SCORECARD_REMINDER = "scorecard_reminder"
    CANDIDATE_MENTION = "candidate_mention"


class EmailRecipient(BaseModel):
    """Email recipient details."""
    email: EmailStr
    name: Optional[str] = None


class EmailMessage(BaseModel):
    """Email message structure."""
    to: List[EmailRecipient]
    cc: Optional[List[EmailRecipient]] = None
    bcc: Optional[List[EmailRecipient]] = None
    subject: str
    html_content: str
    text_content: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    email_type: EmailType
    metadata: Optional[Dict[str, Any]] = None


class EmailService:
    """SendGrid email service for sending transactional emails."""

    def __init__(self):
        self.api_key = settings.sendgrid_api_key
        self.from_email = settings.email_from_address if hasattr(settings, 'email_from_address') else "noreply@bhcorp.com"
        self.from_name = settings.email_from_name if hasattr(settings, 'email_from_name') else "BH Recruiting"
        self.client = SendGridAPIClient(self.api_key) if self.api_key else None

    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return self.client is not None and self.api_key is not None

    async def send_email(self, message: EmailMessage) -> Dict[str, Any]:
        """
        Send an email using SendGrid.

        Returns dict with status and message_id on success, or error details on failure.
        """
        if not self.is_configured():
            logger.warning("Email service not configured. Skipping email send.")
            return {
                "success": False,
                "error": "Email service not configured",
                "simulated": True,
                "message": message.dict()
            }

        try:
            mail = Mail(
                from_email=Email(self.from_email, self.from_name),
                subject=message.subject,
            )

            # Add recipients
            for recipient in message.to:
                mail.add_to(To(recipient.email, recipient.name))

            # Add CC recipients
            if message.cc:
                for cc in message.cc:
                    mail.add_cc(Email(cc.email, cc.name))

            # Add BCC recipients
            if message.bcc:
                for bcc in message.bcc:
                    mail.add_bcc(Email(bcc.email, bcc.name))

            # Add content
            mail.add_content(Content("text/html", message.html_content))
            if message.text_content:
                mail.add_content(Content("text/plain", message.text_content))

            # Add attachments if any
            if message.attachments:
                for att in message.attachments:
                    attachment = Attachment(
                        FileContent(att.get("content", "")),
                        FileName(att.get("filename", "attachment")),
                        FileType(att.get("type", "application/octet-stream")),
                        Disposition("attachment")
                    )
                    mail.add_attachment(attachment)

            # Send email
            response = self.client.send(mail)

            logger.info(
                f"Email sent successfully",
                extra={
                    "email_type": message.email_type,
                    "to": [r.email for r in message.to],
                    "status_code": response.status_code,
                }
            )

            return {
                "success": True,
                "status_code": response.status_code,
                "message_id": response.headers.get("X-Message-Id"),
            }

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}", extra={"email_type": message.email_type})
            return {
                "success": False,
                "error": str(e),
            }

    # Template Methods for Common Email Types

    async def send_interview_scheduled(
        self,
        candidate_email: str,
        candidate_name: str,
        interviewer_names: List[str],
        position_title: str,
        interview_datetime: datetime,
        interview_type: str,  # "phone", "video", "onsite"
        location_or_link: str,
        additional_info: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send interview scheduled notification to candidate."""
        formatted_date = interview_datetime.strftime("%A, %B %d, %Y at %I:%M %p")

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">Interview Scheduled</h2>
            <p>Dear {candidate_name},</p>
            <p>We're excited to confirm your interview for the <strong>{position_title}</strong> position.</p>

            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Date & Time:</strong> {formatted_date}</p>
                <p><strong>Interview Type:</strong> {interview_type.title()}</p>
                <p><strong>{"Location" if interview_type == "onsite" else "Meeting Link"}:</strong> {location_or_link}</p>
                <p><strong>Interviewer(s):</strong> {", ".join(interviewer_names)}</p>
            </div>

            {f"<p><strong>Additional Information:</strong><br>{additional_info}</p>" if additional_info else ""}

            <p>Please reply to this email if you need to reschedule or have any questions.</p>

            <p>Best regards,<br>The Recruiting Team</p>
        </body>
        </html>
        """

        message = EmailMessage(
            to=[EmailRecipient(email=candidate_email, name=candidate_name)],
            subject=f"Interview Scheduled: {position_title}",
            html_content=html_content,
            email_type=EmailType.INTERVIEW_SCHEDULED,
            metadata={
                "position_title": position_title,
                "interview_datetime": interview_datetime.isoformat(),
            }
        )

        return await self.send_email(message)

    async def send_offer_letter(
        self,
        candidate_email: str,
        candidate_name: str,
        position_title: str,
        department: str,
        start_date: datetime,
        salary: float,
        hiring_manager_name: str,
        offer_expiration: Optional[datetime] = None,
        attachment_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send offer letter to candidate."""
        formatted_start = start_date.strftime("%B %d, %Y")
        formatted_salary = f"${salary:,.2f}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #059669;">Congratulations!</h2>
            <p>Dear {candidate_name},</p>
            <p>We are thrilled to extend an offer for you to join our team as a <strong>{position_title}</strong>
            in the {department} department.</p>

            <div style="background-color: #ecfdf5; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Offer Details</h3>
                <p><strong>Position:</strong> {position_title}</p>
                <p><strong>Department:</strong> {department}</p>
                <p><strong>Start Date:</strong> {formatted_start}</p>
                <p><strong>Annual Salary:</strong> {formatted_salary}</p>
                <p><strong>Reporting To:</strong> {hiring_manager_name}</p>
            </div>

            {f"<p><em>This offer expires on {offer_expiration.strftime('%B %d, %Y')}.</em></p>" if offer_expiration else ""}

            <p>Please review the attached offer letter for complete details about compensation, benefits,
            and other terms of employment.</p>

            <p>To accept this offer, please reply to this email or click the link below:</p>
            <p><a href="#" style="background-color: #059669; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Accept Offer</a></p>

            <p>We look forward to welcoming you to the team!</p>

            <p>Best regards,<br>The Recruiting Team</p>
        </body>
        </html>
        """

        message = EmailMessage(
            to=[EmailRecipient(email=candidate_email, name=candidate_name)],
            subject=f"Offer Letter: {position_title}",
            html_content=html_content,
            email_type=EmailType.OFFER_EXTENDED,
            metadata={
                "position_title": position_title,
                "salary": salary,
                "start_date": start_date.isoformat(),
            }
        )

        if attachment_content:
            message.attachments = [{
                "content": attachment_content,
                "filename": f"Offer_Letter_{candidate_name.replace(' ', '_')}.pdf",
                "type": "application/pdf"
            }]

        return await self.send_email(message)

    async def send_application_status_update(
        self,
        candidate_email: str,
        candidate_name: str,
        position_title: str,
        new_status: str,
        custom_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send application status update to candidate."""
        status_messages = {
            "reviewed": "Your application has been reviewed by our team.",
            "screening": "You've been moved to the screening phase.",
            "interview": "You've been selected for an interview! We'll be in touch with scheduling details.",
            "offer": "Great news! We'd like to extend an offer to you.",
            "rejected": "After careful consideration, we've decided to move forward with other candidates.",
            "withdrawn": "Your application has been withdrawn as requested.",
        }

        status_message = custom_message or status_messages.get(new_status, f"Your application status has been updated to: {new_status}")

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">Application Update</h2>
            <p>Dear {candidate_name},</p>
            <p>We wanted to update you on your application for the <strong>{position_title}</strong> position.</p>

            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p>{status_message}</p>
            </div>

            <p>Thank you for your interest in joining our team.</p>

            <p>Best regards,<br>The Recruiting Team</p>
        </body>
        </html>
        """

        message = EmailMessage(
            to=[EmailRecipient(email=candidate_email, name=candidate_name)],
            subject=f"Application Update: {position_title}",
            html_content=html_content,
            email_type=EmailType.APPLICATION_STATUS_UPDATE,
            metadata={
                "position_title": position_title,
                "new_status": new_status,
            }
        )

        return await self.send_email(message)

    async def send_sla_alert(
        self,
        recruiter_email: str,
        recruiter_name: str,
        alert_level: str,  # "amber" or "red"
        job_title: str,
        job_id: str,
        days_remaining: int,
        sla_days: int,
        candidates_in_pipeline: int,
    ) -> Dict[str, Any]:
        """Send SLA alert to recruiter."""
        alert_color = "#f59e0b" if alert_level == "amber" else "#dc2626"
        alert_label = "Warning" if alert_level == "amber" else "Critical"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: {alert_color}; color: white; padding: 15px; text-align: center;">
                <h2 style="margin: 0;">SLA {alert_label} Alert</h2>
            </div>

            <p>Dear {recruiter_name},</p>
            <p>This is an automated alert regarding your assigned job opening:</p>

            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Position:</strong> {job_title}</p>
                <p><strong>Job ID:</strong> {job_id}</p>
                <p><strong>SLA:</strong> {sla_days} days</p>
                <p><strong>Days Remaining:</strong> <span style="color: {alert_color}; font-weight: bold;">{days_remaining} days</span></p>
                <p><strong>Candidates in Pipeline:</strong> {candidates_in_pipeline}</p>
            </div>

            <p>{"Please prioritize this requisition to meet the SLA deadline." if alert_level == "amber" else "Immediate action is required to address this requisition."}</p>

            <p><a href="#" style="background-color: {alert_color}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">View Job Details</a></p>

            <p>Best regards,<br>HR System</p>
        </body>
        </html>
        """

        email_type = EmailType.SLA_AMBER_ALERT if alert_level == "amber" else EmailType.SLA_RED_ALERT

        message = EmailMessage(
            to=[EmailRecipient(email=recruiter_email, name=recruiter_name)],
            subject=f"[{alert_label.upper()}] SLA Alert: {job_title}",
            html_content=html_content,
            email_type=email_type,
            metadata={
                "job_id": job_id,
                "alert_level": alert_level,
                "days_remaining": days_remaining,
            }
        )

        return await self.send_email(message)

    async def send_scorecard_reminder(
        self,
        interviewer_email: str,
        interviewer_name: str,
        candidate_name: str,
        position_title: str,
        interview_date: datetime,
    ) -> Dict[str, Any]:
        """Send reminder to interviewer to submit scorecard."""
        formatted_date = interview_date.strftime("%B %d, %Y")

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">Scorecard Reminder</h2>
            <p>Dear {interviewer_name},</p>
            <p>This is a friendly reminder to submit your interview feedback for:</p>

            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Candidate:</strong> {candidate_name}</p>
                <p><strong>Position:</strong> {position_title}</p>
                <p><strong>Interview Date:</strong> {formatted_date}</p>
            </div>

            <p>Your feedback is essential for making timely hiring decisions. Please submit your scorecard at your earliest convenience.</p>

            <p><a href="#" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Submit Scorecard</a></p>

            <p>Thank you!</p>

            <p>Best regards,<br>The Recruiting Team</p>
        </body>
        </html>
        """

        message = EmailMessage(
            to=[EmailRecipient(email=interviewer_email, name=interviewer_name)],
            subject=f"Reminder: Submit Scorecard for {candidate_name}",
            html_content=html_content,
            email_type=EmailType.SCORECARD_REMINDER,
            metadata={
                "candidate_name": candidate_name,
                "position_title": position_title,
            }
        )

        return await self.send_email(message)

    async def send_mention_notification(
        self,
        mentioned_user_email: str,
        mentioned_user_name: str,
        mentioner_name: str,
        candidate_name: str,
        comment_preview: str,
    ) -> Dict[str, Any]:
        """Send notification when user is @mentioned in a comment."""
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb;">You were mentioned</h2>
            <p>Dear {mentioned_user_name},</p>
            <p><strong>{mentioner_name}</strong> mentioned you in a comment on <strong>{candidate_name}</strong>'s profile:</p>

            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #2563eb;">
                <p style="margin: 0; font-style: italic;">"{comment_preview}"</p>
            </div>

            <p><a href="#" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">View Comment</a></p>

            <p>Best regards,<br>The Recruiting Team</p>
        </body>
        </html>
        """

        message = EmailMessage(
            to=[EmailRecipient(email=mentioned_user_email, name=mentioned_user_name)],
            subject=f"{mentioner_name} mentioned you in a comment",
            html_content=html_content,
            email_type=EmailType.CANDIDATE_MENTION,
            metadata={
                "mentioner_name": mentioner_name,
                "candidate_name": candidate_name,
            }
        )

        return await self.send_email(message)


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service

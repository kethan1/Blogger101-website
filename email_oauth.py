from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def load_credentials_from_file(token_file_path):
    creds = Credentials.from_authorized_user_file(
        token_file_path, ["https://www.googleapis.com/auth/gmail.send"]
    )
    return build("gmail", "v1", credentials=creds)


def load_credentials_from_dict(token_dict):
    creds = Credentials.from_authorized_user_info(
        token_dict, ["https://www.googleapis.com/auth/gmail.send"]
    )
    return build("gmail", "v1", credentials=creds)


def create_message(sender, receiver, subject, message_text, message_html=None):
    """Create a message for an email.

    Args:
      sender: Email address of the sender.
      to: Email address of the receiver.
      subject: The subject of the email message.
      message_text: The text of the email message.

    Returns:
      An object containing a base64url encoded email object.
    """
    if message_html is None:
        message_html = message_text

    message = MIMEMultipart('alternative')
    message["to"] = receiver
    message["from"] = sender
    message["subject"] = subject
    part1 = MIMEText(message_text, 'plain')
    part2 = MIMEText(message_html, 'html')

    message.attach(part1)
    message.attach(part2)

    return {"raw": base64.urlsafe_b64encode(message.as_string().encode()).decode()}


def send_message(service, message):
    """Send an email message.

    Args:
      service: Authorized Gmail API service instance.
      message: Message to be sent.
    """
    service.users().messages().send(userId="me", body=message).execute()


# Sample Usage:
# send_message(load_credentials_from_file("credential path"), create_message("Display Name <sender email>", "reciever email", "subject", "message content"))

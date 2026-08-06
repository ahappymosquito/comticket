"""职责：提供无副作用的 SMTP 邮件客户端封装。"""

from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import os
import smtplib
import ssl

from loguru import logger


class MailClient:
    """发送支持 UTF-8 标题、正文和附件的 SMTP 邮件。"""

    def __init__(
        self,
        smtp_server: str,
        port: int,
        sender_email: str,
        password: str,
        sender_name: str | None = None,
    ) -> None:
        self.smtp_server = smtp_server
        self.port = port
        self.sender_email = sender_email
        self.password = password
        self.sender_name = sender_name or sender_email

    @staticmethod
    def _encode_header(text: str) -> str:
        """将邮件标题编码为 RFC 兼容的 UTF-8 字符串。"""
        return str(Header(text, "utf-8"))

    @staticmethod
    def _encode_addr(name: str, email: str) -> str:
        """编码带显示名称的邮箱地址。"""
        return formataddr((str(Header(name, "utf-8")), email))

    def send_mail(
        self,
        to: list[str] | str,
        subject: str,
        body: str = "",
        html: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        attachments: list[str] | None = None,
    ) -> None:
        """发送邮件；附件路径不存在时跳过该附件并记录警告。"""
        recipients = [to] if isinstance(to, str) else list(to)
        cc = cc or []
        bcc = bcc or []
        attachments = attachments or []

        message = MIMEMultipart("mixed")
        message["From"] = self._encode_addr(self.sender_name, self.sender_email)
        message["To"] = ", ".join(self._encode_addr("", address) for address in recipients)
        if cc:
            message["Cc"] = ", ".join(self._encode_addr("", address) for address in cc)
        message["Subject"] = self._encode_header(subject)

        alternatives = MIMEMultipart("alternative")
        if body:
            alternatives.attach(MIMEText(body, "plain", "utf-8"))
        if html:
            alternatives.attach(MIMEText(html, "html", "utf-8"))
        message.attach(alternatives)

        for file_path in attachments:
            if not os.path.exists(file_path):
                logger.warning("附件不存在: {}", file_path)
                continue
            with open(file_path, "rb") as file:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(file.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(file_path)}"',
            )
            message.attach(part)

        all_recipients = recipients + cc + bcc
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_server, self.port, context=context) as server:
                server.login(self.sender_email, self.password)
                server.sendmail(self.sender_email, all_recipients, message.as_string())
            logger.success("邮件已发送 -> {}", ", ".join(all_recipients))
        except Exception as exc:
            logger.error("邮件发送失败: {}", exc)

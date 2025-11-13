from loguru import logger
import smtplib, ssl, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from email.utils import formataddr

class MailClient:
    """SMTP邮件发送封装，支持UTF-8标题/姓名自动编码"""

    def __init__(self, smtp_server: str, port: int, sender_email: str, password: str, sender_name: str = None):
        self.smtp_server = smtp_server
        self.port = port
        self.sender_email = sender_email
        self.password = password
        self.sender_name = sender_name or sender_email

    def _encode_header(self, text: str) -> str:
        """自动UTF-8安全编码（支持中日韩字符）"""
        return str(Header(text, "utf-8"))

    def _encode_addr(self, name: str, email: str) -> str:
        """带姓名的邮箱格式编码"""
        return formataddr((str(Header(name, "utf-8")), email))

    def send_mail(
        self,
        to: list | str,
        subject: str,
        body: str = "",
        html: str = None,
        cc: list | None = None,
        bcc: list | None = None,
        attachments: list | None = None,
    ):
        try:
            if isinstance(to, str):
                to = [to]
            cc = cc or []
            bcc = bcc or []
            attachments = attachments or []

            # --- 构建邮件 ---
            msg = MIMEMultipart("mixed")
            msg["From"] = self._encode_addr(self.sender_name, self.sender_email)
            msg["To"] = ", ".join([self._encode_addr("", x) for x in to])
            if cc:
                msg["Cc"] = ", ".join([self._encode_addr("", x) for x in cc])
            msg["Subject"] = self._encode_header(subject)

            # --- 正文部分 ---
            alt = MIMEMultipart("alternative")
            if body:
                alt.attach(MIMEText(body, "plain", "utf-8"))
            if html:
                alt.attach(MIMEText(html, "html", "utf-8"))
            msg.attach(alt)

            # --- 附件部分 ---
            for file_path in attachments:
                if not os.path.exists(file_path):
                    logger.warning(f"附件不存在: {file_path}")
                    continue
                with open(file_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{os.path.basename(file_path)}"',
                    )
                    msg.attach(part)

            all_recipients = to + cc + bcc
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_server, self.port, context=context) as server:
                server.login(self.sender_email, self.password)
                server.sendmail(self.sender_email, all_recipients, msg.as_string())

            logger.success(f"✅ 邮件已发送 -> {', '.join(all_recipients)}")

        except Exception as e:
            logger.error(f"❌ 邮件发送失败: {e}")

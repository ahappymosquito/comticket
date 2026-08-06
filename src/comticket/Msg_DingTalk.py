"""职责：封装带签名的钉钉机器人文本消息发送能力。"""

import base64
import hashlib
import hmac
import time
import urllib.parse

import requests
from loguru import logger


class DingTalkBot:
    """钉钉自定义机器人客户端。"""

    def __init__(self, access_token: str, secret: str) -> None:
        self.access_token = access_token
        self.secret = secret

    def _generate_sign(self) -> tuple[str, str]:
        """生成钉钉机器人需要的时间戳和签名。"""
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        digest = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(digest))
        return timestamp, sign

    def send_text(
        self,
        msg: str,
        at_user_ids: list[str] | None = None,
        at_mobiles: list[str] | None = None,
        is_at_all: bool = False,
    ) -> dict:
        """发送文本消息；失败时返回统一的错误字典。"""
        timestamp, sign = self._generate_sign()
        url = (
            "https://oapi.dingtalk.com/robot/send"
            f"?access_token={self.access_token}&timestamp={timestamp}&sign={sign}"
        )
        payload = {
            "msgtype": "text",
            "text": {"content": msg},
            "at": {
                "isAtAll": is_at_all,
                "atUserIds": at_user_ids or [],
                "atMobiles": at_mobiles or [],
            },
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            logger.info("钉钉消息发送成功: {}", data)
            return data
        except requests.RequestException as exc:
            logger.error("钉钉消息发送失败: {}", exc)
            return {"errcode": -1, "errmsg": str(exc)}

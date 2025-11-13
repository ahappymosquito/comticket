from loguru import logger
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests

class DingTalkBot:
    """
    钉钉自定义机器人封装类
    https://open.dingtalk.com/document/orgapp/obtain-the-webhook-address-of-a-custom-robot
    """

    def __init__(self, access_token: str, secret: str):
        """
        初始化机器人实例
        :param access_token: 机器人 webhook 的 access_token
        :param secret: 机器人安全设置中的 secret
        """
        self.access_token = access_token
        self.secret = secret

    def _generate_sign(self) -> tuple[str, str]:
        """生成签名与时间戳"""
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f'{timestamp}\n{self.secret}'
        hmac_code = hmac.new(self.secret.encode('utf-8'),
                             string_to_sign.encode('utf-8'),
                             digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    def send_text(self, msg: str,
                  at_user_ids: list[str] | None = None,
                  at_mobiles: list[str] | None = None,
                  is_at_all: bool = False) -> dict:
        """
        发送文本消息到钉钉群
        :param msg: 消息内容
        :param at_user_ids: @ 的用户ID列表
        :param at_mobiles: @ 的手机号列表
        :param is_at_all: 是否 @ 所有人
        :return: 钉钉 API 响应
        """
        timestamp, sign = self._generate_sign()
        url = (
            f'https://oapi.dingtalk.com/robot/send'
            f'?access_token={self.access_token}&timestamp={timestamp}&sign={sign}'
        )

        payload = {
            "msgtype": "text",
            "text": {"content": msg},
            "at": {
                "isAtAll": is_at_all,
                "atUserIds": at_user_ids or [],
                "atMobiles": at_mobiles or []
            }
        }

        headers = {'Content-Type': 'application/json'}
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"钉钉消息发送成功：{data}")
            return data
        except requests.RequestException as e:
            logger.error(f"钉钉消息发送失败：{e}")
            return {"errcode": -1, "errmsg": str(e)}


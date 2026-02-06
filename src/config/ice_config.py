import base64
import hashlib
import hmac
import os
import time
from typing import Any, Dict, List

from aiortc import RTCIceServer


class ICEConfig:
    """ICE服务器配置管理类"""

    def __init__(self):
        # 默认STUN服务器
        self.default_stun_urls = [
            # "stun:stun.miwifi.com:3478",
            "stun:stun.l.google.com:19302",
            "stun:stun1.l.google.com:19302",
            # "stun:stun.stunprotocol.org:3478",
        ]
        
        # 从环境变量读取TURN服务器配置
        self.turn_url = os.getenv("TURN_SERVER_URL")
        self.turn_username = os.getenv("TURN_USERNAME")
        self.turn_credential = os.getenv("TURN_PASSWORD")
        if self.turn_url:
            self.default_stun_urls.append(self.turn_url.replace("turn:", "stun:"))
        
        # TURN服务器密钥（用于生成临时凭证）
        # 如果使用coturn等支持REST API的TURN服务器，使用共享密钥
        self.turn_secret = os.getenv("TURN_SECRET")
        
        # 凭证有效期（秒），默认24小时
        self.credential_ttl = int(os.getenv("TURN_CREDENTIAL_TTL", "86400"))
    
    def _generate_turn_credentials(self, username_prefix: str = "user") -> tuple[str, str]:
        """
        生成时间限制的TURN凭证（基于RFC 5389）
        
        Args:
            username_prefix: 用户名前缀，可以用于标识客户端
            
        Returns:
            (username, credential) 元组
        """
        if not self.turn_secret:
            # 如果没有配置密钥，使用静态凭证（不推荐）
            return self.turn_username, self.turn_credential
        
        # 计算过期时间戳
        expiry_timestamp = int(time.time()) + self.credential_ttl
        
        # 生成用户名：timestamp:username_prefix
        username = f"{expiry_timestamp}:{username_prefix}"
        
        # 使用HMAC-SHA1生成密码
        hmac_obj = hmac.new(
            self.turn_secret.encode('utf-8'),
            username.encode('utf-8'),
            hashlib.sha1
        )
        credential = base64.b64encode(hmac_obj.digest()).decode('utf-8')
        
        return username, credential

    def get_ice_config(self, client_id: str = "anonymous") -> Dict[str, Any]:
        """
        获取前端ICE配置
        
        Args:
            client_id: 客户端标识（可以是IP、MAC地址或会话ID）
        """
        ice_servers = []

        # 添加默认STUN服务器
        for url in self.default_stun_urls:
            ice_servers.append({"urls": url})

        # 如果配置了TURN服务器，则添加（使用临时凭证）
        if self.turn_url:
            # 生成临时凭证
            username, credential = self._generate_turn_credentials(client_id)
            
            turn_config = {
                "urls": self.turn_url,
                "username": username,
                "credential": credential
            }
            ice_servers.append(turn_config)
        
        return {
            "iceServers": ice_servers, 
            "iceCandidatePoolSize": 10, 
            "iceTransportPolicy": "all", 
            "bundlePolicy": "max-bundle"
        }

    def get_server_ice_servers(self) -> List[RTCIceServer]:
        """获取服务器端ICE服务器对象"""
        servers = []

        # 添加默认STUN服务器
        for url in self.default_stun_urls:
            servers.append(RTCIceServer(urls=url))

        # 如果配置了 TURN 服务器，则添加
        if self.turn_url:
            turn_kwargs = {"urls": self.turn_url}
            if self.turn_username:
                turn_kwargs["username"] = self.turn_username
            if self.turn_credential:
                turn_kwargs["credential"] = self.turn_credential
            servers.append(RTCIceServer(**turn_kwargs))

        return servers


# 全局实例
ice_config = ICEConfig()

import os
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
            "stun:stun.stunprotocol.org:3478",
        ]
        
        # 从环境变量读取TURN服务器配置
        self.turn_url = os.getenv("TURN_SERVER_URL")
        self.turn_username = os.getenv("TURN_USERNAME")
        self.turn_credential = os.getenv("TURN_PASSWORD")

    def get_ice_config(self) -> Dict[str, Any]:
        """获取前端ICE配置"""
        ice_servers = []

        # 添加默认STUN服务器
        for url in self.default_stun_urls:
            ice_servers.append({"urls": url})

        # 如果配置了TURN服务器，则添加
        if self.turn_url:
            turn_config = {"urls": self.turn_url}
            if self.turn_username:
                turn_config["username"] = self.turn_username
            if self.turn_credential:
                turn_config["credential"] = self.turn_credential
            ice_servers.append(turn_config)

        return {"iceServers": ice_servers, "iceCandidatePoolSize": 10, "iceTransportPolicy": "all", "bundlePolicy": "max-bundle"}

    def get_server_ice_servers(self) -> List[RTCIceServer]:
        """获取服务器端ICE服务器对象"""
        servers = []

        # 添加默认STUN服务器
        for url in self.default_stun_urls:
            servers.append(RTCIceServer(urls=url))

        # 如果配置了TURN服务器，则添加
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

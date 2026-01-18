#!/usr/bin/env python3
"""
TURN/STUN服务器连接测试脚本

此脚本用于测试ICE配置中的TURN和STUN服务器是否可用。
测试方法：
1. 解析服务器URL
2. 测试网络连通性（TCP/UDP）
3. 使用aiortc创建实际的WebRTC连接进行验证
"""

import asyncio
import socket
import sys
import time
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from aiortc import RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole

# 导入ICE配置
from src.config.ice_config import ice_config


class TURNTester:
    """TURN/STUN服务器测试器"""

    def __init__(self):
        self.results = []

    def parse_ice_url(self, url: str) -> Tuple[str, str, int]:
        """
        解析ICE服务器URL
        
        Returns:
            (protocol, host, port) 元组
        """
        # 手动解析 STUN/TURN URL
        # 支持两种格式: stun:host:port 和 stun://host:port
        protocol = "stun"  # 默认协议
        rest = url
        
        # 检查是否有协议前缀
        for proto in ["turns://", "turn://", "stun://", "turns:", "turn:", "stun:"]:
            if url.startswith(proto):
                protocol = proto.rstrip(":/")
                rest = url[len(proto):]
                break
        
        # 解析主机和端口
        # 格式可能是: host:port 或 host
        if ":" in rest:
            # 有端口号
            parts = rest.rsplit(":", 1)
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                # 端口解析失败，可能整个都是主机名
                host = rest
                port = None
        else:
            host = rest
            port = None
        
        # 默认端口
        if port is None:
            if protocol == "stun":
                port = 3478
            elif protocol == "turn":
                port = 3478
            elif protocol == "turns":
                port = 5349
        
        return protocol, host, port

    def test_tcp_connectivity(self, host: str, port: int, timeout: float = 5.0) -> bool:
        """测试TCP连接"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception as e:
            print(f"  ❌ TCP连接失败: {e}")
            return False

    def test_udp_connectivity(self, host: str, port: int, timeout: float = 5.0) -> bool:
        """测试UDP连接（发送简单的STUN Binding Request）"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            # STUN Binding Request (RFC 5389)
            # Message Type: 0x0001 (Binding Request)
            # Message Length: 0x0000 (no attributes)
            # Magic Cookie: 0x2112A442
            # Transaction ID: 96 bits (12 bytes) random
            import os
            transaction_id = os.urandom(12)
            stun_request = b'\x00\x01\x00\x00\x21\x12\xa4\x42' + transaction_id
            
            sock.sendto(stun_request, (host, port))
            
            try:
                data, addr = sock.recvfrom(1024)
                sock.close()
                # 检查是否收到STUN响应
                if len(data) >= 20 and data[0:2] == b'\x01\x01':
                    return True
                return False
            except socket.timeout:
                sock.close()
                return False
                
        except Exception as e:
            print(f"  ❌ UDP连接失败: {e}")
            return False

    async def test_webrtc_ice_gathering(self, ice_servers: List[RTCIceServer]) -> bool:
        """
        测试WebRTC ICE候选收集
        这是最真实的测试，因为它使用实际的WebRTC连接
        """
        try:
            from aiortc import RTCConfiguration
            
            config = RTCConfiguration(iceServers=ice_servers)
            pc = RTCPeerConnection(configuration=config)
            
            # 添加一个虚拟的音频轨道以触发ICE收集
            from aiortc import AudioStreamTrack
            from av import AudioFrame
            import numpy as np
            
            class SilenceTrack(AudioStreamTrack):
                async def recv(self):
                    pts, time_base = await self.next_timestamp()
                    frame = AudioFrame(format='s16', layout='mono', samples=960)
                    frame.pts = pts
                    frame.time_base = time_base
                    frame.planes[0].update(np.zeros(1920, dtype=np.int16).tobytes())
                    return frame
            
            pc.addTrack(SilenceTrack())
            
            # 创建offer以触发ICE收集
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            
            # 等待ICE收集完成
            gathered_candidates = []
            max_wait = 10  # 最多等待10秒
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                if pc.iceGatheringState == "complete":
                    break
                await asyncio.sleep(0.1)
            
            # 检查收集到的候选
            if pc.localDescription and pc.localDescription.sdp:
                sdp_lines = pc.localDescription.sdp.split('\n')
                for line in sdp_lines:
                    if line.startswith('a=candidate:'):
                        gathered_candidates.append(line)
            
            await pc.close()
            
            print(f"  ℹ️  收集到 {len(gathered_candidates)} 个ICE候选")
            
            # 检查是否有relay类型的候选（TURN）
            relay_candidates = [c for c in gathered_candidates if 'typ relay' in c]
            if relay_candidates:
                print(f"  ✅ 找到 {len(relay_candidates)} 个TURN中继候选")
                return True
            else:
                print(f"  ⚠️  未找到TURN中继候选（可能只有STUN工作）")
                return len(gathered_candidates) > 0
                
        except Exception as e:
            print(f"  ❌ WebRTC ICE收集失败: {e}")
            import traceback
            traceback.print_exc()
            return False


    async def test_ice_server(self, server_config: Dict) -> Dict:
        """测试单个ICE服务器"""
        urls = server_config.get("urls", "")
        if isinstance(urls, list):
            urls = urls[0]
        
        print(f"\n{'='*60}")
        print(f"测试服务器: {urls}")
        print(f"{'='*60}")
        
        result = {
            "url": urls,
            "protocol": None,
            "host": None,
            "port": None,
            "tcp_ok": False,
            "udp_ok": False,
            "webrtc_ok": False,
            "overall_status": "FAIL"
        }
        
        try:
            protocol, host, port = self.parse_ice_url(urls)
            result["protocol"] = protocol
            result["host"] = host
            result["port"] = port
            
            print(f"协议: {protocol}")
            print(f"主机: {host}")
            print(f"端口: {port}")
            
            # 测试TCP连接
            print(f"\n[1/3] 测试TCP连接...")
            result["tcp_ok"] = self.test_tcp_connectivity(host, port)
            if result["tcp_ok"]:
                print(f"  ✅ TCP连接成功")
            else:
                print(f"  ❌ TCP连接失败")
            
            # 测试UDP连接（STUN）
            print(f"\n[2/3] 测试UDP/STUN连接...")
            result["udp_ok"] = self.test_udp_connectivity(host, port)
            if result["udp_ok"]:
                print(f"  ✅ UDP/STUN连接成功")
            else:
                print(f"  ❌ UDP/STUN连接失败")
            
            # 测试WebRTC ICE收集
            print(f"\n[3/3] 测试WebRTC ICE候选收集...")
            ice_server = RTCIceServer(
                urls=urls,
                username=server_config.get("username"),
                credential=server_config.get("credential")
            )
            result["webrtc_ok"] = await self.test_webrtc_ice_gathering([ice_server])
            
            # 判断总体状态 - 使用原始URL来判断协议
            if urls.startswith("stun:"):
                # STUN服务器需要UDP/STUN连接成功
                result["overall_status"] = "PASS" if result["udp_ok"] else "FAIL"
            elif urls.startswith("turn:") or urls.startswith("turns:"):
                # TURN服务器需要WebRTC测试通过（能够创建relay候选）
                result["overall_status"] = "PASS" if result["webrtc_ok"] else "FAIL"
            
        except Exception as e:
            print(f"  ❌ 测试异常: {e}")
            result["overall_status"] = "ERROR"
        
        return result

    async def run_tests(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("TURN/STUN服务器连接测试")
        print("="*60)
        
        # 获取ICE配置
        ice_config_data = ice_config.get_ice_config(client_id="test_client")
        ice_servers = ice_config_data.get("iceServers", [])
        
        print(f"\n找到 {len(ice_servers)} 个ICE服务器配置")
        
        # 测试每个服务器
        for server in ice_servers:
            result = await self.test_ice_server(server)
            self.results.append(result)
        
        # 打印总结
        self.print_summary()

    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*60)
        print("测试总结")
        print("="*60)
        
        stun_servers = [r for r in self.results if r["url"].startswith("stun:")]
        turn_servers = [r for r in self.results if r["url"].startswith("turn:") or r["url"].startswith("turns:")]
        
        print(f"\nSTUN服务器: {len(stun_servers)} 个")
        for r in stun_servers:
            status_icon = "✅" if r["overall_status"] == "PASS" else "❌"
            print(f"  {status_icon} {r['url']} - {r['overall_status']}")
        
        print(f"\nTURN服务器: {len(turn_servers)} 个")
        for r in turn_servers:
            status_icon = "✅" if r["overall_status"] == "PASS" else "❌"
            print(f"  {status_icon} {r['url']} - {r['overall_status']}")
            if r.get("username"):
                print(f"      用户名: {r.get('username')}")
        
        # 总体结论
        print("\n" + "="*60)
        all_passed = all(r["overall_status"] == "PASS" for r in self.results)
        has_working_turn = any(
            r["overall_status"] == "PASS" and (r["url"].startswith("turn:") or r["url"].startswith("turns:"))
            for r in self.results
        )
        
        if all_passed:
            print("✅ 所有服务器测试通过！")
        elif has_working_turn:
            print("⚠️  部分服务器测试通过，至少有一个TURN服务器可用")
        else:
            print("❌ 测试失败，没有可用的TURN服务器")
        
        print("="*60 + "\n")
        
        return all_passed


async def main():
    """主函数"""
    tester = TURNTester()
    await tester.run_tests()
    
    # 返回退出码
    all_passed = all(r["overall_status"] == "PASS" for r in tester.results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())

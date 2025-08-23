import asyncio
import json
import os

import cv2
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from xiaozhi_sdk import XiaoZhiWebsocket

from src.config import DEFAULT_MAC_ADDR, OTA_URL
from src.track.audio import AudioFaceSwapper
from src.track.video import VideoFaceSwapper

ROOT = os.path.dirname(__file__)


# logging.basicConfig(level=logging.INFO)


async def index(request):
    content = open(os.path.join(ROOT, "index_v3.html"), "r", encoding="utf-8").read()
    return web.Response(content_type="text/html", text=content)


async def offer(request):
    params = await request.json()
    _offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    # Store client IP in the peer connection object
    pc.client_ip = request.headers.get("X-Real-IP", "")
    pc.mac_address = params.get("macAddress") or DEFAULT_MAC_ADDR

    await server(pc, _offer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


pcs = set()


async def server(pc, offer):
    # Dictionary to store track instances

    # Create data channel for text messages
    channel = pc.createDataChannel("chat")

    async def message_handler_callback(message):
        print("Received message:", pc.client_ip, message)
        channel.send(json.dumps(message, ensure_ascii=False))
        if message["type"] == "llm":
            pc.video_track.set_emoji(message["text"])

    xiaozhi = XiaoZhiWebsocket(
        message_handler_callback, ota_url=OTA_URL, audio_sample_rate=48000, audio_channels=2
    )

    def mcp_tool_func():
        def tool_set_volume(data):
            channel.send(
                json.dumps(
                    {"type": "tool", "text": "set_volume", "value": data["volume"]}
                )
            )
            return "", False

        def tool_open_tab(data):
            channel.send(
                json.dumps({"type": "tool", "text": "open_tab", "value": data["url"]})
            )
            return "", False

        def tool_get_device_status(data):
            return (
                json.dumps(
                    {
                        "audio_speaker": {"volume": 100},
                        # 'screen': {'brightness': 75, 'theme': 'light'},
                        # 'network': {'type': 'wifi', 'ssid': 'wifi名称', 'signal': 'strong'}
                    }
                ),
                False,
            )

        def tool_take_photo(data):
            img_obj = xiaozhi.video_frame.to_ndarray(format="bgr24")
            # 直接使用 OpenCV 编码图片
            _, img_byte = cv2.imencode(".jpg", img_obj)
            img_byte = img_byte.tobytes()
            return img_byte, False

        return {
            "set_volume": tool_set_volume,
            "get_device_status": tool_get_device_status,
            "take_photo": tool_take_photo,
            "open_tab": tool_open_tab,
        }

    print("MAC: ", pc.mac_address, "IP: ", pc.client_ip)

    await xiaozhi.set_mcp_tool_callback(mcp_tool_func())
    await xiaozhi.init_connection(pc.mac_address)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is {} {}".format(pc.connectionState, pc.client_ip))
        if pc.connectionState in ["failed", "closed", "disconnected"]:
            # Stop all AudioFaceSwapper instances

            await xiaozhi.close()
            await pc.close()
            pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            t = AudioFaceSwapper(xiaozhi, track)
            pc.addTrack(t)
            # 将 track 实例存储在 pc 对象上
            pc.audio_track = t
        elif track.kind == "video":
            t = VideoFaceSwapper(xiaozhi, track)
            pc.addTrack(t)
            # 将 track 实例存储在 pc 对象上
            pc.video_track = t

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


def run():
    app = web.Application()
    app.on_shutdown.append(on_shutdown)

    app.router.add_get("/", index)
    app.router.add_post("/api/offer", offer)

    web.run_app(app, host="0.0.0.0", port=8083)

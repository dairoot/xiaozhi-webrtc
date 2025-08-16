import os

import cv2
from aiortc import VideoStreamTrack
from av import VideoFrame


class VideoFaceSwapper(VideoStreamTrack):
    kind = "video"

    def __init__(self, xiaozhi, track):
        super().__init__()
        self.track = track
        self.xiaozhi = xiaozhi

        # 加载图片
        self.image_dict = {}
        self.init_image()
        self.image = self.image_dict["default"]

    def init_image(self):
        image_path = os.path.join(os.path.dirname(__file__), "..", "image", "{}")
        self.image_dict = {
            "default": cv2.imread(image_path.format("szr.png")),
            "😄": cv2.imread(image_path.format("szr-happy.png")),
            "😌": cv2.imread(image_path.format("szr-happy.png")),
            "😋": cv2.imread(image_path.format("szr-happy.png")),
            "😊": cv2.imread(image_path.format("szr-happy.png")),
            "😆": cv2.imread(image_path.format("szr-happy.png")),
            "😂": cv2.imread(image_path.format("szr-joy.png")),
            "😭": cv2.imread(image_path.format("szr-joy.png")),
            "😱": cv2.imread(image_path.format("szr-panic.png")),
            "😡": cv2.imread(image_path.format("szr-angry.png")),
            "🥰": cv2.imread(image_path.format("szr-love.png")),
            "😍": cv2.imread(image_path.format("szr-love.png")),
            "😏": cv2.imread(image_path.format("szr-smirk.png")),
            "😉": cv2.imread(image_path.format("szr-smirk.png")),
            "😘": cv2.imread(image_path.format("szr-kiss.png")),
            "😴": cv2.imread(image_path.format("szr-sleep.png")),
            "😎": cv2.imread(image_path.format("szr-cool-2.png")),
            "😔": cv2.imread(image_path.format("szr-sad.png")),
        }

    def set_emoji(self, emoji):
        self.image = self.image_dict.get(emoji, self.image_dict["default"])

    async def recv(self):
        frame = await self.track.recv()
        self.xiaozhi.video_frame = frame

        # 使用加载的图片创建视频帧
        new_frame = VideoFrame.from_ndarray(self.image, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base

        return new_frame

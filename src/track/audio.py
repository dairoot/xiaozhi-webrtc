from fractions import Fraction

import av
import numpy as np
from aiortc import AudioStreamTrack

resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)


class AudioFaceSwapper(AudioStreamTrack):
    kind = "audio"

    def __init__(self, xiaozhi, track):
        super().__init__()
        self.track = track
        self.sample_rate = 48000
        self.xiaozhi = xiaozhi

    def empty_frame(self):
        samples = np.zeros(960, dtype=np.float32)
        samples = (samples * 32767).astype(np.int16)
        new_frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1), format="s16", layout="mono"
        )
        new_frame.sample_rate = self.sample_rate
        new_frame.pts = 0
        return new_frame

    async def recv(self):
        original_frame = await self.track.recv()
        pcm_data = np.frombuffer(original_frame.planes[0], dtype=np.int16)
        await self.xiaozhi.send_audio(pcm_data.tobytes())

        if self.xiaozhi.output_audio_queue:
            samples = self.xiaozhi.output_audio_queue.popleft()

            # 创建一个新的音频帧
            new_frame = av.AudioFrame.from_ndarray(
                samples.reshape(1, -1),
                format="s16",
                layout="mono",
            )
            new_frame.sample_rate = self.sample_rate
            new_frame.pts = original_frame.pts
            new_frame.time_base = Fraction(1, self.sample_rate)

            return new_frame

        return self.empty_frame()

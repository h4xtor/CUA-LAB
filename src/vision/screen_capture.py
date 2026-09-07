import mss
from PIL import Image
from loguru import logger

class ScreenCapture:
    def __init__(self):
        self.sct = mss.mss()
        logger.info("📸 Screen capture klar")
    async def capture(self, monitor: int = 1) -> Image.Image:
        monitors = self.sct.monitors
        screenshot = self.sct.grab(monitors[monitor])
        return Image.frombytes('RGB', screenshot.size, screenshot.bgra, 'raw', 'BGRX')

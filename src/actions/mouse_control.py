import asyncio
import pyautogui
from loguru import logger

class MouseController:
    def __init__(self):
        pyautogui.FAILSAFE = True
        logger.info("🖱️ Mouse controller klar")
    async def click(self, x: int, y: int):
        logger.info(f"🖱️ Klikker på ({x}, {y})")
        await asyncio.get_event_loop().run_in_executor(None, pyautogui.click, x, y)

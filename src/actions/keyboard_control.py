import asyncio
import pyautogui
from loguru import logger

class KeyboardController:
    def __init__(self):
        logger.info("⌨️ Keyboard controller klar")
    async def type(self, text: str):
        logger.info(f"⌨️ Skriver: {text}")
        await asyncio.get_event_loop().run_in_executor(None, pyautogui.write, text)

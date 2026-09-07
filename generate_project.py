import os

PROJECT_FILES = {
    "requirements.txt": """pyqt6>=6.6.0
pyqtdarktheme>=2.1.0
ollama>=0.1.6
pyautogui>=0.9.54
mss>=9.0.1
pillow>=10.2.0
opencv-python>=4.9.0
playwright>=1.41.0
chromadb>=0.4.22
sentence-transformers>=2.3.1
python-dotenv>=1.0.0
loguru>=0.7.2
psutil>=5.9.8
""",
    "config.py": """from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SafetyConfig:
    require_confirmation_for: List[str] = None
    max_actions_per_minute: int = 60
    blocked_keys: List[str] = None
    def __post_init__(self):
        if self.require_confirmation_for is None: self.require_confirmation_for = ['delete', 'format', 'sudo', 'rm']
        if self.blocked_keys is None: self.blocked_keys = ['ctrl+alt+delete', 'alt+f4']

@dataclass
class AppConfig:
    app_name: str = "OmniRoute Ultimate"
    debug: bool = True
    base_path: Path = Path(__file__).parent
    data_path: Path = Path("./data")
    logs_path: Path = Path("./data/logs")
    safety: SafetyConfig = None
    def __post_init__(self):
        if self.safety is None: self.safety = SafetyConfig()
        for path in [self.data_path, self.logs_path]: path.mkdir(parents=True, exist_ok=True)

config = AppConfig()
""",
    ".env.example": """OLLAMA_BASE_URL=http://localhost:11434
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
DEBUG=true
""",
    "src/__init__.py": "",
    "src/core/__init__.py": "",
    "src/core/agent.py": """import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger
from config import config

class OmniRouteAgent:
    def __init__(self):
        logger.info("🚀 Initialiserer OmniRoute Ultimate Agent...")
        self.is_running = False
        self.current_task: Optional[str] = None
        logger.info("✅ Agent initialiseret")
    
    async def execute_task(self, task_description: str) -> Dict[str, Any]:
        logger.info(f"📋 Starter opgave: {task_description}")
        self.is_running = True
        self.current_task = task_description
        await asyncio.sleep(1) # Simulerer arbejde
        self.is_running = False
        return {"success": True, "task": task_description, "duration_seconds": 1.0}
        
    def stop(self):
        self.is_running = False
""",
    "src/core/orchestrator.py": """from loguru import logger
class ModelOrchestrator:
    def __init__(self):
        logger.info("🧠 Model Orchestrator klar")
    async def generate(self, prompt: str, model_name: str = "gemma:7b") -> str:
        return f"Simuleret svar fra {model_name}"
""",
    "src/core/safety.py": """from loguru import logger
class SafetyGuard:
    def __init__(self):
        logger.info("🛡️ Safety guard initialiseret")
    def approve_action(self, action: dict) -> bool:
        action_type = action.get('action', 'unknown')
        if action_type in ['delete', 'format', 'sudo']:
            logger.warning(f"⚠️ Action blokeret: {action_type}")
            return False
        return True
""",
    "src/core/memory.py": """from loguru import logger
class VectorMemory:
    def __init__(self):
        logger.info("💾 Vector Memory klar")
""",
    "src/vision/__init__.py": "",
    "src/vision/screen_capture.py": """import mss
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
""",
    "src/actions/__init__.py": "",
    "src/actions/mouse_control.py": """import asyncio
import pyautogui
from loguru import logger

class MouseController:
    def __init__(self):
        pyautogui.FAILSAFE = True
        logger.info("🖱️ Mouse controller klar")
    async def click(self, x: int, y: int):
        logger.info(f"🖱️ Klikker på ({x}, {y})")
        await asyncio.get_event_loop().run_in_executor(None, pyautogui.click, x, y)
""",
    "src/actions/keyboard_control.py": """import asyncio
import pyautogui
from loguru import logger

class KeyboardController:
    def __init__(self):
        logger.info("⌨️ Keyboard controller klar")
    async def type(self, text: str):
        logger.info(f"⌨️ Skriver: {text}")
        await asyncio.get_event_loop().run_in_executor(None, pyautogui.write, text)
""",
    "src/learning/__init__.py": "",
    "src/learning/experience_buffer.py": """from loguru import logger
class ExperienceBuffer:
    def __init__(self):
        logger.info("📚 Experience buffer initialiseret")
""",
    "src/ui/__init__.py": "",
    "src/ui/main_window.py": """import sys
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QApplication
import qdarktheme
from loguru import logger

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OmniRoute Ultimate - Computer Use AI Agent")
        self.resize(800, 600)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        title = QLabel("🚀 OmniRoute Ultimate")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #8b5cf6;")
        layout.addWidget(title)
        status = QLabel("Klar til at automatisere din computer!")
        layout.addWidget(status)
        logger.info("🎨 UI initialiseret")
""",
    "main.py": """import sys
import asyncio
from loguru import logger
from config import config
from src.ui.main_window import MainWindow
import qdarktheme

def setup_logging():
    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>", level="INFO")
    logger.info("🚀 OmniRoute Ultimate starter...")

def main():
    setup_logging()
    try:
        app = QApplication(sys.argv)
        qdarktheme.setup_theme("auto")
        window = MainWindow()
        window.show()
        logger.info("✅ OmniRoute Ultimate klar!")
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"❌ Kritisk fejl: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
""",
    "README.md": """# ⚡ OmniRoute Ultimate
**Verdens mest avancerede open-source Computer-Use AI Agent**

## 🚀 Kom godt i gang
1. `pip install -r requirements.txt`
2. `playwright install`
3. `ollama pull llava:13b`
4. `python main.py`

## 🏗️ Arkitektur
- `src/core/`: Hoved agent og orchestration
- `src/vision/`: Screen capture og analyse
- `src/actions/`: Mouse, keyboard, browser control
- `src/learning/`: Memory og experience buffer
- `src/ui/`: PyQt6 interface
""",
    ".gitignore": """__pycache__/
*.py[cod]
venv/
env/
.env
data/
*.log
.DS_Store
Thumbs.db
"""
}

def create_project():
    print("🚀 Opretter OmniRoute Ultimate projektstruktur...")
    for filepath, content in PROJECT_FILES.items():
        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Oprettet: {filepath}")
    
    print("\n" + "="*60)
    print("🎉 PROJEKTET ER SUCCESFULDT GENERERET!")
    print("="*60)
    print("\nKør nu følgende kommandoer i din terminal for at committe og pushe:")
    print("-" * 60)
    print("git init")
    print("git add .")
    print('git commit -m "feat: Initial commit - OmniRoute Ultimate Computer-Use AI Agent"')
    print("git branch -M main")
    print("git remote add origin https://github.com/h4xtor/Computer-Use-LLM.git")
    print("git push -u origin main")
    print("-" * 60)

if __name__ == "__main__":
    create_project()
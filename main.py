import sys
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

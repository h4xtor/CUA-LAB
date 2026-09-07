import sys
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

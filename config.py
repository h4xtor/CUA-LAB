from pathlib import Path
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

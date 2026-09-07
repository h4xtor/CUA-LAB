from loguru import logger
class SafetyGuard:
    def __init__(self):
        logger.info("🛡️ Safety guard initialiseret")
    def approve_action(self, action: dict) -> bool:
        action_type = action.get('action', 'unknown')
        if action_type in ['delete', 'format', 'sudo']:
            logger.warning(f"⚠️ Action blokeret: {action_type}")
            return False
        return True

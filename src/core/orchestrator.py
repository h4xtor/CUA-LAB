from loguru import logger
class ModelOrchestrator:
    def __init__(self):
        logger.info("🧠 Model Orchestrator klar")
    async def generate(self, prompt: str, model_name: str = "gemma:7b") -> str:
        return f"Simuleret svar fra {model_name}"

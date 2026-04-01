from main.src.utils.llms.gemini.DRGeminiWrapper import asyncGenerateContent, _safe_json_loads


class GeminiComponents:
    def __init__(self, gemini: Any) -> None:
        self.gemini = gemini

    async def generate_content(self, prompt: str, system: str, model: str, image: Optional[Image.Image] = None) -> str:
        return await asyncGenerateContent(prompt, system, model, image, self.gemini)

    async def generate_content_with_schema(self, prompt: str, system: str, model: str, image: Optional[Image.Image] = None, json_schema: Optional[Dict[str, Any]] = None) -> str:
        return await asyncGenerateContent(prompt, system, model, image, self.gemini, json_schema)
    
    async def think_on_topic_lightly(self, context: str, topic: str) -> str:
        system_instruction = """You are a Research Assistant. Your job is to think on a topic lightly and generate a response."""
        prompt = f"""Context: {context}
Topic: {topic}

Think on the topic lightly and generate a response."""
        return await self.generate_content(prompt, system_instruction, "gemini-2.5-flash-lite")
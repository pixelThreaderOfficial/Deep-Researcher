import requests


class FastSummarizer:
    def __init__(
        self,
        model: str = "qwen3.5:9b",
        base_url: str = "http://localhost:11434/api/generate",
        max_words: int = 1000,
    ):
        self.model = model
        self.base_url = base_url
        self.max_words = max_words

    # -----------------------------
    # 🔹 Trim text (THE MVP MAGIC)
    # -----------------------------
    def _trim_text(self, text: str) -> str:
        words = text.split()
        return " ".join(words[: self.max_words])

    # -----------------------------
    # 🔹 Ollama call
    # -----------------------------
    def _generate(self, prompt: str) -> str:
        res = requests.post(
            self.base_url,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.2, "num_predict": 800},
            },
        )

        if res.status_code != 200:
            raise Exception(res.text)

        return res.json()["response"].strip()

    # -----------------------------
    # 🔹 Public API
    # -----------------------------
    def summarize(self, text: str) -> str:
        trimmed = self._trim_text(text)

        prompt = f"""
        You are a professional concise summarizer.

        Create a **dense, information-rich, and concise** summary of the following text.

        Instructions:
        - Be concise: Remove redundancy, filler words, and repetition.
        - Be comprehensive: Keep all key ideas, important features, main findings, methods, results, and conclusions.
        - Maintain accuracy and technical depth where it matters.
        - Use short sentences or bullet points only when they make the summary clearer and more scannable.
        - Prioritize information density — every sentence should carry value.

        TEXT:
        {trimmed}

        Return only the summary. Do not add any meta comments.
        """
        return self._generate(prompt)

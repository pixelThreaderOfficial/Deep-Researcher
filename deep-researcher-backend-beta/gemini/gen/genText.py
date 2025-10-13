from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

MODEL_NAME = "gemini-2.0-flash"


load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_content(prompt: str, thinking: bool = False):
    response = client.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        thinking=thinking,
    )
    return response.text


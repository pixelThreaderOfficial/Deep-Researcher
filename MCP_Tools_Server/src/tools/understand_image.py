import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Union

import aiohttp
from ollama import AsyncClient
from PIL import Image
from pydantic import BaseModel

from sse.event_bus import event_bus
from utils.logger.AgentLogger import quickLog
from utils.task_scheduler import scheduler

# ---------------------------
# CONFIG
# ---------------------------
TEMP_DIR = Path(__file__).parent.parent / "temp"
os.makedirs(TEMP_DIR, exist_ok=True)


# ---------------------------
# Schema
# ---------------------------
class ImageSummary(BaseModel):
    title: str
    desc: str


# ---------------------------
# Helpers
# ---------------------------
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def generate_image_name(index: int, title: str, ext: str) -> str:
    words = title.split()[:8]

    safe_words = [
        w.lower().strip(".,!?()[]{}\"'").replace("/", "") for w in words if w.strip()
    ]

    joined = "_".join(safe_words) or "image"

    return f"{ordinal(index)}_image_{joined}.{ext}"


# ---------------------------
# Download Image
# ---------------------------
async def download_image(url: str) -> str:
    filename = f"{uuid.uuid4()}"
    filepath = os.path.join(TEMP_DIR, filename)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(await resp.read())

    print(f"[DOWNLOADED] -> {filepath}")
    return filepath


# ---------------------------
# Resize + Convert
# ---------------------------
def process_image(input_path: str) -> str:
    img = Image.open(input_path)

    if img.mode != "RGB":
        img = img.convert("RGB")

    if img.size[0] > 600 or img.size[1] > 600:
        img.thumbnail((600, 600), Image.LANCZOS)

    output_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}.jpg")
    img.save(output_path, format="JPEG", quality=85)

    print(f"[PROCESSED] -> {output_path}")
    return output_path


# ---------------------------
# CORE MULTI IMAGE TOOL
# ---------------------------
async def understand_images(
    image_inputs: Union[str, List[str]],
    prompt_raw: Optional[str] = None,
    ollama_host: Optional[str] = None,
) -> Dict:

    host = ollama_host or "http://localhost:11434"

    if isinstance(image_inputs, str):
        image_inputs = [image_inputs]

    total_files = len(image_inputs)
    success_count = 0

    results = {}

    total_tokens = 0
    total_time = 0

    client = AsyncClient(host=host)

    system_prompt = (
        "You are an image analysis AI. Carefully examine the image and generate "
        "a concise title under 10 words and description under 100 words. "
        "Respond strictly in JSON with keys 'title' and 'desc'."
    )

    async def process_single(image_input, index):
        nonlocal success_count, total_tokens, total_time

        start_time = time.time()
        original_path = image_input
        processed_path = None

        try:
            await scheduler.schedule(
                quickLog,
                params={
                    "level": "info",
                    "message": f"Processing image: {image_input}",
                    "module": ["AI"],
                    "urgency": "none",
                },
            )

            # ---------------------------
            # Download if URL
            # ---------------------------
            is_url = isinstance(image_input, str) and image_input.startswith("http")

            if is_url:
                original_path = await download_image(image_input)

            # ---------------------------
            # Process image
            # ---------------------------
            processed_path = process_image(original_path)

            # ---------------------------
            # LLM CALL
            # ---------------------------
            response = await client.generate(
                model="gemma4:e2b",
                prompt=prompt_raw or "Analyze the image",
                system=system_prompt,
                think=False,
                format=ImageSummary.model_json_schema(),
                images=[processed_path],
                stream=False,
                keep_alive=True,
            )

            result = ImageSummary.model_validate_json(response.response)

            elapsed = round(time.time() - start_time, 3)

            tokens = estimate_tokens(result.title + " " + result.desc)

            total_tokens += tokens
            total_time += elapsed
            success_count += 1

            # ---------------------------
            # NAMING LOGIC (🔥 IMPORTANT)
            # ---------------------------
            ext = Path(processed_path).suffix.replace(".", "")

            if is_url:
                filename = generate_image_name(index, result.title, ext)
            else:
                filename = Path(image_input).name

            # ---------------------------
            # STORE RESULT
            # ---------------------------
            results[filename] = {
                "title": result.title,
                "desc": result.desc,
                "tokens": tokens,
                "time": elapsed,
                "stored_at": processed_path,
            }

            await event_bus.broadcast(
                message={
                    "msg": "Image processed",
                    "tool_param": image_input,
                    "tool_result": results[filename],
                }
            )

            await scheduler.schedule(
                quickLog,
                params={
                    "level": "success",
                    "message": f"Processed image: {image_input}",
                    "module": ["AI"],
                    "urgency": "none",
                },
            )

        except Exception as e:
            results[str(image_input)] = "fail to process this file"

            await scheduler.schedule(
                quickLog,
                params={
                    "level": "error",
                    "message": f"Failed image: {str(e)}",
                    "module": ["AI"],
                    "urgency": "moderate",
                },
            )

    await asyncio.gather(
        *(process_single(img, idx + 1) for idx, img in enumerate(image_inputs))
    )

    return {
        "total_files": total_files,
        "succeed": success_count,
        "total_tokens_used": total_tokens,
        "total_time_taken": round(total_time, 3),
        "content": results,
    }


# ---------------------------
# TEST
# ---------------------------
if __name__ == "__main__":

    async def main():
        test_input = [
            "https://custom-images.strikinglycdn.com/res/hrscywv4p/image/upload/c_limit,fl_lossy,h_9000,w_1200,f_auto,q_auto/42473/DSC_0294_zathos.jpg",
            "/home/pixelthreader/Downloads/6usp7r28_most-detailed-image-of-moon-shared-by-photographer_625x300_12_May_23.jpg",
            "/home/pixelthreader/Downloads/sun.jpg",
        ]

        result = await understand_images(
            image_inputs=test_input, ollama_host="http://localhost:11434"
        )

        print("\n🔥 RESULT:")
        print(result)

    asyncio.run(main())

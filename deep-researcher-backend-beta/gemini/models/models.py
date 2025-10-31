from datetime import datetime
import json


def datetime_to_str(obj):
    """Convert datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat() if obj else None
    return obj


MODELS_LIST = [
    {
        "name": "Gemini 2.5 Pro",
        "provider": "Google",
        "provider_type": "online",
        "tag": "OUR MOST ADVANCED MODEL",
        "description": "According to Google, this is their state-of-the-art thinking model, capable of reasoning over complex problems in code, math, and STEM, as well as analyzing large datasets, codebases, and documents using long context.",
        "pricing_docs": "https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-pro",
        "docs": "https://ai.google.dev/gemini-api/docs/models#gemini-2.5-pro",
        "code": "gemini-2.5-pro",
        "suported_inputs": ["text", "image", "audio", "video", "pdf"],
        "supported_outputs": ["text"],
        "input_token_limit": 1048576,
        "output_token_limit": 65536,
        "capabilities": {
            "audio": False,
            "batch_api": True,
            "caching": True,
            "code_execution": True,
            "function_calling": True,
            "image_generation": False,
            "live_api": False,
            "search_grounding": True,
            "structured_outputs": True,
            "thinking": [
                True,
                {
                    "toggle": False,
                    "min_tokens": 128,
                    "max_tokens": 32768,
                    "capabilities": "Dynamic Thinking: set `thinkingBudget = -1` to enable dynamic thinking, where the model will automatically decides when and how much to think",
                },
            ],
            "url_context": True,
        },
        "stable_release_version": "gemini-2.5-pro",
        "latest_update": datetime(2025, 6, 1),
        "knowledge_cutoff": datetime(2025, 1, 1),
    },
    {
        "name": "Gemini 2.5 Pro Preview TTS",
        "provider": "Google",
        "provider_type": "cloud",
        "tag": "OUR MOST ADVANCED MODEL",
        "description": "According to Google, this is their state-of-the-art thinking model, capable of reasoning over complex problems in code, math, and STEM, as well as analyzing large datasets, codebases, and documents using long context.",
        "pricing_docs": "https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-pro",
        "docs": "https://ai.google.dev/gemini-api/docs/models#gemini-2.5-pro",
        "code": "gemini-2.5-pro-preview-tts",
        "suported_inputs": ["text"],
        "supported_outputs": ["audio"],
        "input_token_limit": 8000,
        "output_token_limit": 16000,
        "capabilities": {
            "audio": True,
            "batch_api": True,
            "caching": False,
            "code_execution": False,
            "function_calling": False,
            "image_generation": False,
            "live_api": False,
            "search_grounding": False,
            "structured_outputs": False,
            "thinking": [False, {}],
            "url_context": False,
        },
        "stable_release_version": "gemini-2.5-pro-preview-tts",
        "latest_update": datetime(2025, 6, 1),
        "knowledge_cutoff": None,
    },
    {
        "name": "Gemini 2.5 Flash",
        "provider": "Google",
        "provider_type": "cloud",
        "tag": "FAST AND INTELLIGENT",
        "description": "According to Google, this is their best model in terms of price-performance, offering well-rounded capabilities. 2.5 Flash is best for large scale processing, low-latency, high volume tasks that require thinking, and agentic use cases.",
        "pricing_docs": "https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash",
        "docs": "https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash",
        "code": "gemini-2.5-flash",
        "suported_inputs": ["text", "image", "audio", "video"],
        "supported_outputs": ["text"],
        "input_token_limit": 1048576,
        "output_token_limit": 65536,
        "capabilities": {
            "audio": False,
            "batch_api": True,
            "caching": True,
            "code_execution": True,
            "function_calling": True,
            "image_generation": False,
            "live_api": False,
            "search_grounding": True,
            "structured_outputs": True,
            "thinking": [
                True,
                {
                    "toggle": True,
                    "min_tokens": 0,
                    "max_tokens": 24576,
                    "capabilities": "Dynamic Thinking: set `thinkingBudget = -1` to enable dynamic thinking, where the model will automatically decides when and how much to think. Set `thinkingBudget = 0` to disable any thinking.",
                },
            ],
            "url_context": True,
        },
        "stable_release_version": "gemini-2.5-flash",
        "latest_update": datetime(2025, 6, 1),
        "knowledge_cutoff": datetime(2025, 1, 1),
    },
    {
        "name": "Gemini 2.5 Flash Preview 09-2025",
        "provider": "Google",
        "provider_type": "cloud",
        "tag": "FAST AND INTELLIGENT",
        "description": "According to Google, this is their best model in terms of price-performance, offering well-rounded capabilities. 2.5 Flash is best for large scale processing, low-latency, high volume tasks that require thinking, and agentic use cases.",
        "pricing_docs": "https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash",
        "docs": "https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash",
        "code": "gemini-2.5-flash-preview-09-2025",
        "suported_inputs": ["text", "image", "audio", "video"],
        "supported_outputs": ["text"],
        "input_token_limit": 1048576,
        "output_token_limit": 65536,
        "capabilities": {
            "audio": False,
            "batch_api": True,
            "caching": True,
            "code_execution": True,
            "function_calling": True,
            "image_generation": False,
            "live_api": False,
            "search_grounding": True,
            "structured_outputs": True,
            "thinking": [
                True,
                {
                    "toggle": True,
                    "min_tokens": 0,
                    "max_tokens": 24576,
                    "capabilities": "Dynamic Thinking: set `thinkingBudget = -1` to enable dynamic thinking, where the model will automatically decides when and how much to think. Set `thinkingBudget = 0` to disable any thinking.",
                },
            ],
            "url_context": True,
        },
        "stable_release_version": "gemini-2.5-flash-preview-09-2025",
        "latest_update": datetime(2025, 9, 1),
        "knowledge_cutoff": datetime(2025, 1, 1),
    },
    {
        "name": "Gemini 2.5 Flash Image",
        "provider": "Google",
        "provider_type": "cloud",
        "tag": "FAST AND INTELLIGENT",
        "description": "According to Google, this is their best model in terms of price-performance, offering well-rounded capabilities. 2.5 Flash is best for large scale processing, low-latency, high volume tasks that require thinking, and agentic use cases.",
        "pricing_docs": "https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash",
        "docs": "https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash",
        "code": "gemini-2.5-flash-image",
        "suported_inputs": ["text", "image"],
        "supported_outputs": ["text", "image"],
        "input_token_limit": 32768,
        "output_token_limit": 32768,
        "capabilities": {
            "audio": False,
            "batch_api": True,
            "caching": True,
            "code_execution": False,
            "function_calling": False,
            "image_generation": True,
            "live_api": False,
            "search_grounding": False,
            "structured_outputs": True,
            "thinking": [False, {}],
            "url_context": False,
        },
        "stable_release_version": "gemini-2.5-flash-image",
        "latest_update": datetime(2025, 10, 1),
        "knowledge_cutoff": datetime(2025, 6, 1),
    },
    {
        "name": "Gemini 2.5 Flash Preview TTS",
        "provider": "Google",
        "provider_type": "cloud",
        "tag": "FAST AND INTELLIGENT",
        "description": "According to Google, this is their state-of-the-art thinking model, capable of reasoning over complex problems in code, math, and STEM, as well as analyzing large datasets, codebases, and documents using long context.",
        "pricing_docs": "https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash",
        "docs": "https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash",
        "code": "gemini-2.5-flash-preview-tts",
        "suported_inputs": ["text"],
        "supported_outputs": ["audio"],
        "input_token_limit": 8000,
        "output_token_limit": 16000,
        "capabilities": {
            "audio": True,
            "batch_api": True,
            "caching": False,
            "code_execution": False,
            "function_calling": False,
            "image_generation": False,
            "live_api": False,
            "search_grounding": False,
            "structured_outputs": False,
            "thinking": [False, {}],
            "url_context": False,
        },
        "stable_release_version": "gemini-2.5-flash-preview-tts",
        "latest_update": datetime(2025, 5, 1),
        "knowledge_cutoff": None,
    },
    {
        "name": "Gemini 2.5 Flash-Lite",
        "provider": "Google",
        "provider_type": "cloud",
        "tag": "ULTRA FAST",
        "description": "According to Google, this is their fastest flash model optimized for cost-efficiency and high throughput.",
        "pricing_docs": "https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash-lite",
        "docs": "https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash-lite",
        "code": "gemini-2.5-flash-lite",
        "suported_inputs": ["text", "image", "audio", "video", "pdf"],
        "supported_outputs": ["text"],
        "input_token_limit": 1048576,
        "output_token_limit": 65536,
        "capabilities": {
            "audio": False,
            "batch_api": True,
            "caching": True,
            "code_execution": True,
            "function_calling": True,
            "image_generation": False,
            "live_api": False,
            "search_grounding": True,
            "structured_outputs": True,
            "thinking": [
                True,
                {
                    "toggle": True,
                    "min_tokens": 512,
                    "max_tokens": 24576,
                    "capabilities": "Dynamic Thinking: set `thinkingBudget = -1` to enable dynamic thinking, where the model will automatically decides when and how much to think. Set `thinkingBudget = 0` to disable any thinking.",
                },
            ],
            "url_context": True,
        },
        "stable_release_version": "gemini-2.5-flash-lite",
        "latest_update": datetime(2025, 7, 1),
        "knowledge_cutoff": datetime(2025, 1, 1),
    },
    {
        "name": "Gemini 2.5 Flash-Lite Preview 09-2025",
        "provider": "Google",
        "provider_type": "cloud",
        "tag": "ULTRA FAST",
        "description": "According to Google, this is their best model in terms of price-performance, offering well-rounded capabilities. 2.5 Flash is best for large scale processing, low-latency, high volume tasks that require thinking, and agentic use cases.",
        "pricing_docs": "https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash-lite",
        "docs": "https://ai.google.dev/gemini-api/docs/models#gemini-2.5-flash-lite",
        "code": "gemini-2.5-flash-lite-preview-09-2025",
        "suported_inputs": ["text", "image"],
        "supported_outputs": ["text", "image"],
        "input_token_limit": 32768,
        "output_token_limit": 32768,
        "capabilities": {
            "audio": False,
            "batch_api": True,
            "caching": True,
            "code_execution": True,
            "function_calling": True,
            "image_generation": False,
            "live_api": False,
            "search_grounding": True,
            "structured_outputs": True,
            "thinking": [
                True,
                {
                    "toggle": True,
                    "min_tokens": 512,
                    "max_tokens": 24576,
                    "capabilities": "Dynamic Thinking: set `thinkingBudget = -1` to enable dynamic thinking, where the model will automatically decides when and how much to think. Set `thinkingBudget = 0` to disable any thinking.",
                },
            ],
            "url_context": True,
        },
        "stable_release_version": "gemini-2.5-flash-lite-preview-09-2025",
        "latest_update": datetime(2025, 9, 1),
        "knowledge_cutoff": datetime(2025, 1, 1),
    },
]


def get_available_models():
    try:
        return MODELS_LIST
    except Exception as e:
        return {"error": "Error getting available models", "message": str(e)}


def get_model_names():
    try:
        return [(model["name"], model["provider"], model["provider_type"], model["code"], model["suported_inputs"], model["supported_outputs"]) for model in MODELS_LIST]
    except Exception as e:
        return {"error": "Error getting model names", "message": str(e)}


def get_model_data_by_code(code: str, as_json: bool = False):
    try:
        for model in MODELS_LIST:
            if model["code"] == code:
                if as_json:
                    return json.dumps(model, default=datetime_to_str, indent=4)
                return model
        raise ValueError(f"Model with code {code} not found")
    except Exception as e:
        return {"error": "Error getting model data by code", "message": str(e)}

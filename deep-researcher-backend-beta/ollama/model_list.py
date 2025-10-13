import ollama
import json
import re
from datetime import datetime

# Provider patterns for regex matching on model names (case insensitive)
provider_patterns = [
    (r"(?i)qwen", "Alibaba"),
    (r"(?i)gemma", "Google"),
    (r"(?i)deepseek", "Deepseek"),
    (r"(?i)phi", "Microsoft"),
    (
        r"(?i)^gpt-(3\.5|4|oss)",
        "OpenAI",
    ),  # Only official OpenAI GPT models (3.5 and 4 series)
    (r"(?i)llama", "Meta"),
    (r"(?i)granite", "IBM"),
    (r"(?i)mistral|mixtral", "Mistral"),
    (r"(?i)claude", "Anthropic"),
    (r"(?i)stable", "Stability AI"),
    (r"(?i)^yi", "Yi"),  # ^yi to avoid matching other models with yi in them
    (r"(?i)nous", "Nous Research"),
    (r"(?i)yi-chat", "01.AI"),
    (r"(?i)grok", "xAI"),
]


def custom_json_serializer(obj):
    """Custom JSON serializer for objects that aren't directly serializable."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    # Try to convert object to dict if it has a __dict__ attribute
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    # For other objects, try to convert to string
    return str(obj)


# Get list of all available models
models_list = ollama.list()
all_models_info = {}


def get_total_models(model_list):
    return len(model_list.models)


def get_all_models_info():
    """Get information for all available models"""
    models_list = ollama.list()
    all_models_info = []

    for model in models_list.models:
        model_name = model.model
        model_info = get_model_info(model_name)
        all_models_info.append(model_info)

    return all_models_info


def get_model_info(model_name):
    try:
        model_info = ollama.show(model_name)
        # Convert to dict for easier access
        model_dict = json.loads(json.dumps(model_info, default=custom_json_serializer))

        # Extract only the essential information
        details = model_dict.get("details", {})
        modelinfo = model_dict.get("modelinfo", {})

        # Find provider by regex matching on model name
        provider = "Unknown"
        for pattern, prov in provider_patterns:
            if re.search(pattern, model_name):
                provider = prov
                break

        return {
            "model": model_name,
            "provider": provider,
            "family": details.get("family", "Unknown"),
            "parameter_size": details.get("parameter_size", "Unknown"),
            "quantization_level": details.get("quantization_level", "Unknown"),
            "architecture": modelinfo.get("general.architecture", "Unknown"),
            "parameter_count": modelinfo.get("general.parameter_count", "Unknown"),
            "modified_at": model_dict.get("modified_at", "Unknown"),
        }
    except Exception as e:
        return {
            "model": model_name,
            "provider": "Unknown",
            "family": "Unknown",
            "parameter_size": "Unknown",
            "quantization_level": "Unknown",
            "architecture": "Unknown",
            "parameter_count": "Unknown",
            "modified_at": "Unknown",
            "error": str(e),
        }


# Get information for all models
all_models = get_all_models_info()
print(json.dumps(all_models, indent=2))


# print(f"Found {len(models_list.models)} models. Gathering information...")

# # Loop through each model and get its information
# for model in models_list.models:
#     model_name = model.model
#     try:
#         print(f"Getting info for: {model_name}")
#         model_info = ollama.show(model_name)
#         # Convert to JSON-serializable format
#         all_models_info[model_name] = json.loads(
#             json.dumps(model_info, default=custom_json_serializer)
#         )
#     except Exception as e:
#         print(f"Error getting info for {model_name}: {e}")
#         all_models_info[model_name] = {"error": str(e)}

# # Convert to JSON with proper formatting
# json_data = json.dumps(all_models_info, indent=4, ensure_ascii=False)

# # Write to file
# with open("all_models_info.json", "w", encoding="utf-8") as f:
#     f.write(json_data)

# print(
#     f"Information for {len(all_models_info)} models saved to all_models_info.json"
# )

# # Also print a summary
# print("\nModel Summary:")
# for model_name, info in all_models_info.items():
#     if "error" not in info:
#         size = info.get("details", {}).get("parameter_size", "Unknown")
#         family = info.get("details", {}).get("family", "Unknown")
#         print(f"- {model_name}: {family} ({size})")
#     else:
#         print(f"- {model_name}: Error - {info['error']}")

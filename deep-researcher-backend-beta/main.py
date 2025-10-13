import ollama
import json
from datetime import datetime


def custom_json_serializer(obj):
    """Custom JSON serializer for objects that aren't directly serializable."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    # Try to convert object to dict if it has a __dict__ attribute
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    # For other objects, try to convert to string
    return str(obj)


def main():
    # Get list of all available models
    models_list = ollama.list()
    all_models_info = {}

    print(f"Found {len(models_list.models)} models. Gathering information...")

    # Loop through each model and get its information
    for model in models_list.models:
        model_name = model.model
        try:
            print(f"Getting info for: {model_name}")
            model_info = ollama.show(model_name)
            # Convert to JSON-serializable format
            all_models_info[model_name] = json.loads(
                json.dumps(model_info, default=custom_json_serializer)
            )
        except Exception as e:
            print(f"Error getting info for {model_name}: {e}")
            all_models_info[model_name] = {"error": str(e)}

    # Convert to JSON with proper formatting
    json_data = json.dumps(all_models_info, indent=4, ensure_ascii=False)

    # Write to file
    with open("all_models_info.json", "w", encoding="utf-8") as f:
        f.write(json_data)

    print(
        f"Information for {len(all_models_info)} models saved to all_models_info.json"
    )

    # Also print a summary
    print("\nModel Summary:")
    for model_name, info in all_models_info.items():
        if "error" not in info:
            size = info.get("details", {}).get("parameter_size", "Unknown")
            family = info.get("details", {}).get("family", "Unknown")
            print(f"- {model_name}: {family} ({size})")
        else:
            print(f"- {model_name}: Error - {info['error']}")


if __name__ == "__main__":
    main()

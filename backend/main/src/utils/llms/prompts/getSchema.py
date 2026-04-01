import json
from pathlib import Path

DIR = Path(__file__).parent

jsonschema = json.load(open(DIR / "json" / "schemas.json", encoding="utf-8"))


def getImageUnderstandingSchema():
    """
    Returns the JSON schema for the image understanding API.

    The returned dictionary describes the structure of objects expected for image analysis tasks, with keys and example values as follows:

    Example output:
        {
            "title": "Title for the image",
            "description": "Description for the image under 100 words",
            "tags": ["tags", "related", "to", "the", "image"],
            "colors": [
                {
                    "color": "color name",
                    "percentage": "percentage of the color in the image"
                },
                {
                    "color": "color name 2",
                    "percentage": "percentage of the color in the image"
                }
            ],
            "objects": [
                "objects",
                "inside",
                "to",
                "the",
                "image"
            ]
        }

    Returns:
        dict: The image_understanding schema loaded from the corresponding JSON file.
    """
    
    return jsonschema["image_understanding"]


def getOllamaImageUnderstandingSchema() -> dict:
    """
    ## Description

    Returns a proper JSON Schema object (RFC-compliant, `type`/`properties`/`required`)
    suitable for use as Ollama's `format` parameter to force structured JSON output
    from vision models. This is **not** interchangeable with `getImageUnderstandingSchema()`
    which returns a Gemini-style example dict.

    ## Parameters

    None

    ## Returns

    `dict`

    Structure:

    ```json
    {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "colors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "color": {"type": "string"},
                        "percentage": {"type": "string"}
                    },
                    "required": ["color", "percentage"]
                }
            },
            "objects": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["title", "description", "tags", "colors", "objects"]
    }
    ```

    ## Raises

    None

    ## Side Effects

    None

    ## Debug Notes

    - Pass this to `aclient.chat(format=getOllamaImageUnderstandingSchema())`.
    - Only use with vision-capable models confirmed by `checkModelCapabilities()`.

    ## Customization

    Extend `properties` with additional keys (e.g., `"mood"`, `"text_detected"`)
    to capture more metadata per image.
    """
    return jsonschema["ollama_image_understanding"]

def getTitleAndDescriptionSchema() -> dict:
    """
    Returns the JSON schema for generating a title and description for content.

    The returned dictionary describes the structure of objects expected for title and description generation tasks, with keys and example values as follows:

    Example output:
        {
            "title": "Title for the content",
            "description": "Description for the content under 100 words"
        }

    Returns:
        dict: The title_and_description schema loaded from the corresponding JSON file.
    """
    return jsonschema["title_and_description"]

def getSummarizationSchema() -> dict:
    """
    Returns the JSON schema for summarization tasks.

    The returned dictionary describes the structure of objects expected for summarization tasks, with keys and example values as follows:

    Example output:
        {
            "summary": "A concise summary of the content in under 100 words."
        }

    Returns:
        dict: The summarize schema loaded from the corresponding JSON file.
    """
    return jsonschema["summarize"]

def getThinkerSchema() -> dict:
    """
    ### Returns the JSON schema for thinking tasks.

    The returned dictionary describes the structure of objects expected for thinking tasks, with keys and example values as follows:

    Example output:
    ```json
        {
            "thought": "A concise summary of the thinking process in under 100 words."
        }
    ```

    Returns:
        dict: The think schema loaded from the corresponding JSON file.
    """
    return jsonschema["thinker"]
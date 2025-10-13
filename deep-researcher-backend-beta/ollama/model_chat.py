from ollama import chat, generate
from ollama import ChatResponse
from datetime import datetime
import json


def custom_json_serializer(obj):
    """Custom JSON serializer for objects that aren't directly serializable."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    # Try to convert object to dict if it has a __dict__ attribute
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    # For other objects, try to convert to string
    return str(obj)


# response: ChatResponse = chat(
#     model="granite3-moe",
#     messages=[
#         {
#             "role": "system",
#             "content": "Your name is Alfred, a helpful assistant. Created by 'pixelThreader' at pixelLabs",
#         },
#         {
#             "role": "user",
#             "content": "Are you granite? and tell me about yourself",
#         },
#     ],
#     keep_alive=False,
# )
# print(response["message"]["content"])
# or access fields directly from the response object
# print(response.message.content)


def generate_content(query: str, system: str = "", model: str = "granite3-moe"):
    response_obj = custom_json_serializer(
        generate(model=model, prompt=query, system=system)
    )
    return response_obj


print(
    json.dumps(
        generate_content(
            system="Your name is Alfred, a helpful assistant. Created by 'pixelThreader' at pixelLabs",
            query="Why Sky is blue",
        ),
        indent=4,
    )
)

# import json
# from datetime import datetime


# def custom_json_serializer(obj):
#     """Custom JSON serializer for objects that aren't directly serializable."""
#     if isinstance(obj, datetime):
#         return obj.isoformat()
#     # Try to convert object to dict if it has a __dict__ attribute
#     if hasattr(obj, "__dict__"):
#         return obj.__dict__
#     # For other objects, try to convert to string
#     return str(obj)


# stream = chat(
#     model="granite3-moe",
#     messages=[
#         {"role": "user", "content": "Are you granite? and tell me about yourself"}
#     ],
#     stream=True,
# )

# for chunk in stream:
#     # Convert chunk to JSON-serializable format
#     serializable_chunk = json.loads(json.dumps(chunk, default=custom_json_serializer))
#     print(json.dumps(serializable_chunk, indent=4), flush=True)


# def get_respose(
#     model: str,
#     query: str,
#     system: str = "You're Alfred, a helpful deep researching AI Agent.",
# ):
#     g

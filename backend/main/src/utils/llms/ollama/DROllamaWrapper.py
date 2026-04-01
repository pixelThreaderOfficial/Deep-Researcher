"""
## Description

The `DROllamaWrapper` module provides synchronous and asynchronous interfaces
to interact with locally hosted Ollama models. It mirrors the API surface of
`DRGeminiWrapper` so that both providers are interchangeable at the caller
level. Supports text generation, streaming, tool/function calling, structured
JSON output, single- and multi-image vision, iterative planning, and plan
updates. All events are logged uniformly to the central DRLogger.

## Parameters

None (Module Level)

## Returns

None (Module Level)

## Raises

- `ConnectionError`
  - When the Ollama server is unreachable at the configured host.
- `ValueError`
  - When generated content is unexpectedly empty.
- `Exception`
  - Wraps generic or unhandled issues from the Ollama SDK.

## Side Effects

- Reads the optional `OLLAMA_HOST` secret from `DRSecrets` (falls back to
  `http://localhost:11434`).
- Logs extensive metadata and model invocation tracking to the system logger.
- Loads image bytes into memory during vision tasks.

## Debug Notes

- Monitor the `OLLAMA_WRAPPER` tag in logs for client initialization and
  generation errors.
- Async variants require `ollama.AsyncClient`.

## Customization

You can change global constants `LOG_SOURCE` or `LOG_TAGS` to route
generation logs differently. Change `DEFAULT_OLLAMA_HOST` to point to a
remote Ollama server.
"""

from ollama import Client, AsyncClient
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Generator,
    List,
    Literal,
    Optional,
)
import json
from pathlib import Path
from main.src.utils.version_constants import get_raw_version
from main.src.utils.llms.prompts.getSchema import getImageUnderstandingSchema, getOllamaImageUnderstandingSchema
from main.src.utils.DRLogger import dr_logger
from main.secrets.DRSecrets import Secrets


LOG_SOURCE = "system"
LOG_TAGS = ["API"]
DEFAULT_OLLAMA_HOST = "http://localhost:11434"


# ---------------------------------------------------------------------------
# Internal logging helper
# ---------------------------------------------------------------------------


def _log_ollama_event(
    message: str,
    level: Literal["success", "error", "warning", "info"] = "info",
    urgency: Literal["none", "moderate", "critical"] = "none",
):
    """
    ## Description

    Internal utility function for logging Ollama wrapper events with structured
    metadata. Ensures all Ollama-related operations are tracked with appropriate
    urgency levels and log sources.

    ## Parameters

    - `message` (`str`)
      - Description: Human-readable description of the Ollama event.
      - Constraints: Must be non-empty. Should not contain sensitive data.
      - Example: "Ollama client initialized successfully."

    - `level` (`Literal["success", "error", "warning", "info"]`)
      - Description: Log severity level indicating the nature of the event.
      - Constraints: Must be one of: "success", "error", "warning", "info".
      - Example: "error"

    - `urgency` (`Literal["none", "moderate", "critical"]`, optional)
      - Description: Priority indicator for the logged event.
      - Constraints: Must be one of: "none", "moderate", "critical".
      - Default: "none"
      - Example: "critical"

    ## Returns

    `None`

    ## Side Effects

    - Writes log entry to the DRLogger system.
    - Includes application version in all log entries.
    - Tags all events with "OLLAMA_WRAPPER" for filtering.

    ## Debug Notes

    - Ensure messages do NOT contain sensitive information.
    - Use appropriate urgency levels: "critical" for connection failures,
      "moderate" for empty responses.
    - Check logger output in application logs directory.

    ## Customization

    To change log source or tags globally, modify the module-level constants:
    - `LOG_SOURCE`: Change from "system" to custom value
    - `LOG_TAGS`: Extend list with additional tags
    """
    dr_logger.log(
        log_type=level,
        message=message,
        origin=LOG_SOURCE,
        urgency=urgency,
        module="API",
        app_version=get_raw_version(),
    )


# ---------------------------------------------------------------------------
# Host resolution helper
# ---------------------------------------------------------------------------


def _resolve_ollama_host() -> str:
    """
    ## Description

    Resolves the Ollama server host URL by checking the secrets manager first,
    falling back to the module-level `DEFAULT_OLLAMA_HOST` constant.

    ## Parameters

    None

    ## Returns

    `str`

    Structure:

    ```json
    "http://localhost:11434"
    ```

    ## Raises

    None

    ## Side Effects

    - Reads the `OLLAMA_HOST` key from `DRSecrets` if available.

    ## Debug Notes

    - If the Ollama server is remote or on a custom port, set `OLLAMA_HOST`
      in your `.env` file.

    ## Customization

    Change `DEFAULT_OLLAMA_HOST` at module level to alter the fallback.
    """
    try:
        secrets = Secrets()
        host = secrets.get_secret("OLLAMA_HOST")
        if host:
            return str(host).strip()
    except Exception:
        pass
    return DEFAULT_OLLAMA_HOST


# ---------------------------------------------------------------------------
# Client initializers
# ---------------------------------------------------------------------------


def getClient() -> Client:
    """
    ## Description

    Initializes and returns the synchronous Ollama client. Kept for parity
    with the Gemini wrapper, but the async client is preferred for
    concurrent workloads.

    ## Parameters

    None

    ## Returns

    `Client`

    Structure:

    ```python
    ollama.Client
    ```

    ## Raises

    - `Exception`
      - When the Ollama server is unreachable or the SDK raises during init.

    ## Side Effects

    - Logs initialization attempts and outcomes to the DRLogger system.

    ## Debug Notes

    - Verify the Ollama server is running (`ollama serve` or system service).
    - Check application logs if initialization fails.

    ## Customization

    None
    """
    _log_ollama_event("Initializing synchronous Ollama Client")
    host = _resolve_ollama_host()
    try:
        _log_ollama_event(f"Attempting connection to Ollama at {host}.")
        client = Client(host=host)
        _log_ollama_event(
            "Synchronous Ollama Client initialized successfully.",
            level="success",
        )
        return client
    except Exception as e:
        _log_ollama_event(str(e), level="error", urgency="critical")
        raise


def getAsyncClient() -> AsyncClient:
    """
    ## Description

    Initializes and returns the asynchronous Ollama client. This is the
    primary client for serving multiple concurrent users via `await`.

    ## Parameters

    None

    ## Returns

    `AsyncClient`

    Structure:

    ```python
    ollama.AsyncClient
    ```

    ## Raises

    - `Exception`
      - When the Ollama server is unreachable or SDK initialization fails.

    ## Side Effects

    - Logs the initialization process using the DRLogger system.

    ## Debug Notes

    - Verify the Ollama server is running on the expected host and port.
    - Check logs for critical errors during creation.

    ## Customization

    None
    """
    _log_ollama_event("Initializing async Ollama Client")
    host = _resolve_ollama_host()
    try:
        _log_ollama_event(f"Attempting async connection to Ollama at {host}.")
        aclient = AsyncClient(host=host)
        _log_ollama_event(
            "Async Ollama Client initialized successfully.", level="success"
        )
        return aclient
    except Exception as e:
        _log_ollama_event(str(e), level="error", urgency="critical")
        raise


# ---------------------------------------------------------------------------
# Model inspection
# ---------------------------------------------------------------------------


async def getModelList(aclient: AsyncClient) -> list[dict]:
    """
    ## Description

    Retrieves a list of all locally available Ollama models. Parses the
    model objects into standard Python dictionaries.

    ## Parameters

    - `aclient` (`AsyncClient`)
      - Description: The asynchronous Ollama client instance.
      - Constraints: Must be properly initialized.
      - Example: `AsyncClient()`

    ## Returns

    `list[dict]`

    Structure:

    ```json
    [
        {
            "name": "gemma3:4b",
            "model": "gemma3:4b",
            "size": 3300000000,
            "digest": "a2af6cc3eb7f"
        }
    ]
    ```

    ## Raises

    - `Exception`
      - When the model listing API call fails (e.g., server unreachable).

    ## Side Effects

    - Logs the retrieval attempt, success count, or failure details.

    ## Debug Notes

    - Validate the async client instance if exceptions are thrown.
    - The returned dicts mirror `ollama ls` output fields.

    ## Customization

    None
    """
    _log_ollama_event("Retrieving list of available Ollama models.")
    try:
        response = await aclient.list()
        models_raw = getattr(response, "models", []) or []
        parsed_models = []
        for model in models_raw:
            try:
                model_dict = model.model_dump(mode="json")
            except AttributeError:
                model_dict = model.__dict__ if hasattr(model, "__dict__") else dict(model)
            parsed_models.append(model_dict)

        _log_ollama_event(
            f"Retrieved {len(parsed_models)} models successfully.",
            level="success",
        )
        return parsed_models

    except Exception as e:
        _log_ollama_event(str(e), level="error", urgency="critical")
        raise


async def getOllamaModel(aclient: AsyncClient, model_name: str = "gemma3:4b") -> dict:
    """
    ## Description

    Retrieves detailed information about a specific Ollama model by name
    using the `show` endpoint.

    ## Parameters

    - `aclient` (`AsyncClient`)
      - Description: The initialized async Ollama client instance.
      - Constraints: Must be valid.
      - Example: `AsyncClient()`

    - `model_name` (`str`)
      - Description: The specific model identifier to inspect.
      - Constraints: Must be a locally available model tag.
      - Example: "gemma3:4b"

    ## Returns

    `dict`

    Structure:

    ```json
    {
        "modelfile": "...",
        "parameters": "...",
        "template": "...",
        "details": {}
    }
    ```

    ## Raises

    - `Exception`
      - If the specified model name is not found locally.

    ## Side Effects

    - Logs the specific model fetch attempt and its resolution.

    ## Debug Notes

    - Run `ollama ls` to verify the model is pulled locally.
    - Validate model tag spelling if an error surfaces.

    ## Customization

    Change the default `model_name` parameter to another preferred local model.
    """
    _log_ollama_event(f"Retrieving Ollama model info: {model_name}")
    try:
        model_info = await aclient.show(model=model_name)
        _log_ollama_event(
            f"Ollama model '{model_name}' info retrieved successfully.",
            level="success",
        )
        try:
            return model_info.model_dump(mode="json")
        except AttributeError:
            return model_info.__dict__ if hasattr(model_info, "__dict__") else dict(model_info)
    except Exception as e:
        _log_ollama_event(str(e), level="error", urgency="critical")
        raise


# ---------------------------------------------------------------------------
# Model capability detection
# ---------------------------------------------------------------------------


async def checkModelCapabilities(
    aclient: AsyncClient,
    model_name: str,
) -> Dict[str, Any]:
    """
    ## Description

    Queries the Ollama `/api/show` endpoint for a specific model and returns
    a structured summary of its declared capabilities. Use this before calling
    vision or thinking-aware functions to confirm the model actually supports
    those features, avoiding runtime 500 errors.

    ## Parameters

    - `aclient` (`AsyncClient`)
      - Description: Async Ollama client instance.
      - Constraints: Must be properly initialized.
      - Example: `AsyncClient()`

    - `model_name` (`str`)
      - Description: The Ollama model tag to inspect.
      - Constraints: Must be a locally available model tag.
      - Example: `"qwen3-vl:2b"`

    ## Returns

    `Dict[str, Any]`

    Structure:

    ```json
    {
        "vision": true,
        "thinking": false,
        "raw_capabilities": ["completion", "vision"]
    }
    ```

    ## Raises

    - `Exception`
      - If the model is not found or the Ollama server is unreachable.

    ## Side Effects

    - Logs the detected capabilities at INFO level.

    ## Debug Notes

    - If a model newly supports vision but this returns `false`, ensure you
      have pulled the latest version with `ollama pull <model>`.
    - The `capabilities` field is returned by Ollama only when `verbose=True`
      is passed to the show endpoint.

    ## Customization

    Extend the returned dict with additional capability keys as Ollama adds
    new capability strings in future versions.
    """
    _log_ollama_event(f"Checking capabilities for model: {model_name}")
    try:
        model_info = await aclient.show(model=model_name)
        raw_caps: list[str] = list(getattr(model_info, "capabilities", []) or [])
        result = {
            "vision": "vision" in raw_caps,
            "thinking": "thinking" in raw_caps,
            "raw_capabilities": raw_caps,
        }
        _log_ollama_event(
            f"Model '{model_name}' capabilities: {raw_caps}",
            level="info",
        )
        return result
    except Exception as e:
        _log_ollama_event(
            f"Failed to retrieve capabilities for '{model_name}': {e}",
            level="error",
            urgency="moderate",
        )
        raise


# ---------------------------------------------------------------------------
# Synchronous generation
# ---------------------------------------------------------------------------


def generateContent(
    prompt: str,
    system: str,
    model: str,
    image: Optional[str],
    client: Client,
    options: Optional[Dict[str, Any]] = None,
) -> str:
    """
    ## Description

    Generates text content synchronously using a specified Ollama model,
    prompt, and optional image.

    ## Parameters

    - `prompt` (`str`)
      - Description: The primary input instruction or text query.
      - Constraints: Must be non-empty.
      - Example: "What is the capital of France?"

    - `system` (`str`)
      - Description: System-level instructions to steer model behavior.
      - Constraints: Can be empty.
      - Example: "You are a helpful geography expert."

    - `model` (`str`)
      - Description: The identifier of the chosen Ollama model.
      - Constraints: Must be a locally available model tag.
      - Example: "gemma3:4b"

    - `image` (`Optional[str]`)
      - Description: Path to an image file for vision models. Optional.
      - Constraints: If provided, model must support vision.
      - Example: "/tmp/photo.jpg"

    - `client` (`Client`)
      - Description: The synchronous Ollama client.
      - Constraints: Must be properly initialized.
      - Example: `Client()`

    ## Returns

    `str`

    Structure:

    ```json
    "Paris is the capital of France."
    ```

    ## Raises

    - `ValueError`
      - When the generated content is empty.
    - `Exception`
      - When the generation API request fails.

    ## Side Effects

    - Logs the generation process and output length.

    ## Debug Notes

    - If getting empty responses, check model availability and prompt safety.
    - Verify image path exists if using a vision model.

    ## Customization

    Modify the `messages` list structure if multi-turn context is needed.
    """
    _log_ollama_event(f"Generating content with model: {model}")

    try:
        messages: List[Dict[str, Any]] = []

        if system:
            messages.append({"role": "system", "content": system})

        user_message: Dict[str, Any] = {"role": "user", "content": prompt}
        if image:
            user_message["images"] = [image]

        messages.append(user_message)

        response = client.chat(
            model=model,
            messages=messages,
            stream=False,
            options=options,
        )

        _log_ollama_event("Content generated successfully.", level="success")

        text = getattr(response, "message", None)
        content = getattr(text, "content", None) if text else None

        if not content:
            _log_ollama_event(
                "Generated content is empty.",
                level="error",
                urgency="moderate",
            )
            raise ValueError("Generated content is empty.")

        return str(content).strip()

    except Exception as e:
        _log_ollama_event(
            f"Content generation failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


def generateContentStream(
    prompt: str,
    system: str,
    model: str,
    image: Optional[str],
    client: Client,
    options: Optional[Dict[str, Any]] = None,
) -> Generator[str, None, None]:
    """
    ## Description

    Generates content iteratively via response streaming, yielding chunks
    of text as they are processed by the specified Ollama model.

    ## Parameters

    - `prompt` (`str`)
      - Description: Primary text prompt for the generation.
      - Constraints: Must be a valid string.
      - Example: "Write a long story about spaceships."

    - `system` (`str`)
      - Description: Guiding system instructions for the model.
      - Constraints: None.
      - Example: "Respond strictly in markdown."

    - `model` (`str`)
      - Description: The generative model identifier.
      - Constraints: Must be a locally available model tag.
      - Example: "gemma3:4b"

    - `image` (`Optional[str]`)
      - Description: Image path for vision models. Optional.
      - Constraints: Model must support vision if provided.
      - Example: None

    - `client` (`Client`)
      - Description: The synchronous Ollama client.
      - Constraints: Proper valid client object.
      - Example: `Client()`

    ## Returns

    `Generator[str, None, None]`

    Structure:

    ```python
    # Iteratively yields string tokens:
    "Once", " upon", " a", " time..."
    ```

    ## Raises

    - `Exception`
      - Raised if the stream breaks or the connection fails.

    ## Side Effects

    - Streams logs reflecting chunk counts and total streaming size.

    ## Debug Notes

    - Empty chunks are skipped and logged. Monitor warnings if output is choppy.
    - Watch for model loading time on first stream request.

    ## Customization

    Add `options` dict to control temperature, top_p, etc.
    """
    _log_ollama_event(f"Starting streaming generation with model: {model}")

    try:
        messages: List[Dict[str, Any]] = []

        if system:
            messages.append({"role": "system", "content": system})

        user_message: Dict[str, Any] = {"role": "user", "content": prompt}
        if image:
            _log_ollama_event("Image content detected. Adding to stream payload.")
            user_message["images"] = [image]

        messages.append(user_message)

        _log_ollama_event(
            f"Prepared contents. Prompt length: {len(prompt)} chars.",
            level="info",
        )

        stream = client.chat(
            model=model,
            messages=messages,
            stream=True,
            options=options,
        )

        _log_ollama_event("Stream connection established.", level="success")

        total_chunks = 0
        total_chars = 0

        for chunk in stream:
            total_chunks += 1

            if not chunk:
                _log_ollama_event(
                    f"Received empty chunk at index {total_chunks}.",
                    level="warning",
                )
                continue

            text = getattr(getattr(chunk, "message", None), "content", None)

            if not text:
                _log_ollama_event(
                    f"Chunk {total_chunks} contained no text.",
                    level="warning",
                )
                continue

            total_chars += len(text)

            _log_ollama_event(
                f"Streaming chunk {total_chunks} ({len(text)} chars).",
                level="info",
            )

            yield text

        _log_ollama_event(
            f"Streaming completed successfully. "
            f"Total chunks: {total_chunks}, Total characters: {total_chars}.",
            level="success",
        )

    except Exception as e:
        _log_ollama_event(
            f"Streaming failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


# ---------------------------------------------------------------------------
# Asynchronous generation
# ---------------------------------------------------------------------------


async def asyncGenerateContent(
    prompt: str,
    system: str,
    model: str,
    image: Optional[str],
    aclient: AsyncClient,
    tools: Optional[List[Any]] = None,
    json_schema: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> str:
    """
    ## Description

    Asynchronously generates text content using an Ollama model with optional
    support for tool calling and JSON schema-constrained output.

    ## Parameters

    - `prompt` (`str`)
      - Description: Main user prompt and request instructions.
      - Constraints: Must be a non-empty string.
      - Example: "Tell me the weather."

    - `system` (`str`)
      - Description: System-level framing and context constraints.
      - Constraints: None natively, but affects inference.
      - Example: "You are a meteorological assistant."

    - `model` (`str`)
      - Description: Name of the Ollama model to use.
      - Constraints: Must be a locally available model tag.
      - Example: "gemma3:4b"

    - `image` (`Optional[str]`)
      - Description: Path to an image for vision models.
      - Constraints: Model must support vision if provided.
      - Example: None

    - `aclient` (`AsyncClient`)
      - Description: The async Ollama client instance.
      - Constraints: Must support the `.chat()` interface.
      - Example: `AsyncClient()`

    - `tools` (`Optional[List[Any]]`, optional)
      - Description: Function tools for automated LLM orchestration.
        Ollama accepts Python callables or JSON schema tool definitions.
      - Constraints: Must match Ollama tool schema requirements.
      - Default: None
      - Example: `[get_weather_function]`

    - `json_schema` (`Optional[Dict[str, Any]]`, optional)
      - Description: JSON schema dict to force structured JSON output via
        Ollama's `format` parameter.
      - Constraints: Dictionary resembling a standard JSON schema object.
      - Default: None
      - Example: `{"type": "object", "properties": {"temp": {"type": "number"}}}`

    ## Returns

    `str`

    Structure:

    ```json
    "{ \"temperature\": 22 }"
    ```

    ## Raises

    - `ValueError`
      - If generated content yields an empty response.
    - `Exception`
      - When async generation calls encounter connection or model faults.

    ## Side Effects

    - Logs asynchronous events sequentially.
    - May inject `format` or `tools` options into the request.

    ## Debug Notes

    - Validate the parameter types of `json_schema` to prevent crashes.
    - Tool handling needs proper definition passing or the model ignores them.

    ## Customization

    Add `options` dict to incorporate temperature, seed, or token caps.
    """
    _log_ollama_event(f"[async] Generating content with model: {model}")

    try:
        messages: List[Dict[str, Any]] = []

        if system:
            messages.append({"role": "system", "content": system})

        user_message: Dict[str, Any] = {"role": "user", "content": prompt}
        if image:
            _log_ollama_event(
                "[async] Image content detected. Adding to payload.", level="info"
            )
            user_message["images"] = [image]

        messages.append(user_message)

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
        }

        if tools:
            _log_ollama_event(
                f"[async] Attaching {len(tools)} tools to request.", level="info"
            )
            kwargs["tools"] = tools

        if json_schema is not None:
            _log_ollama_event(
                "[async] Enabling JSON schema constrained output.", level="info"
            )
            kwargs["format"] = json_schema

        response = await aclient.chat(**kwargs)

        _log_ollama_event(
            "[async] Content generated successfully.", level="success"
        )

        text = getattr(getattr(response, "message", None), "content", None)

        if not text:
            _log_ollama_event(
                "[async] Generated content is empty.",
                level="error",
                urgency="moderate",
            )
            raise ValueError("Generated content is empty.")

        return str(text).strip()

    except Exception as e:
        _log_ollama_event(
            f"[async] Content generation failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


async def asyncGenerateContentStream(
    prompt: str,
    system: str,
    model: str,
    image: Optional[str],
    aclient: AsyncClient,
    tools: Optional[List[Any]] = None,
) -> AsyncGenerator[str, None]:
    """
    ## Description

    Asynchronously generates content via streaming from a specified Ollama
    model. Suitable for high-concurrency web handlers returning chunked
    text back to the client (e.g., FastAPI SSE endpoints).

    ## Parameters

    - `prompt` (`str`)
      - Description: Primary instruction or input payload.
      - Constraints: Must be a valid string query.
      - Example: "Give me ideas for a blog post."

    - `system` (`str`)
      - Description: System-level framing and response configurations.
      - Constraints: None.
      - Example: "Respond strictly in bullet points."

    - `model` (`str`)
      - Description: The specific Ollama model identifier.
      - Constraints: Must be a locally available model tag.
      - Example: "gemma3:4b"

    - `image` (`Optional[str]`)
      - Description: Optional path to an image file.
      - Constraints: Model must support vision if provided.
      - Example: None

    - `aclient` (`AsyncClient`)
      - Description: Asynchronous Ollama client instance.
      - Constraints: Proper valid async client.
      - Example: `AsyncClient()`

    - `tools` (`Optional[List[Any]]`, optional)
      - Description: Function tool specifications.
      - Constraints: Valid structure for Ollama tool ingestion.
      - Default: None
      - Example: `[search_tool]`

    ## Returns

    `AsyncGenerator[str, None]`

    Structure:

    ```python
    # Yields strings:
    "First", " point", " is", " this..."
    ```

    ## Raises

    - `Exception`
      - If the stream generator fails or the connection drops.

    ## Side Effects

    - Outputs incremental log updates highlighting chunk volume and
      characters per iteration.

    ## Debug Notes

    - The `total_chunks` and `total_chars` variables in logs can diagnose
      cut-offs or stream drops early.
    - Watch for model loading time on first request.

    ## Customization

    Add `options` dict to control temperature, seed, num_predict, etc.
    """
    _log_ollama_event(f"[async] Starting streaming generation with model: {model}")

    try:
        messages: List[Dict[str, Any]] = []

        if system:
            messages.append({"role": "system", "content": system})

        user_message: Dict[str, Any] = {"role": "user", "content": prompt}
        if image:
            _log_ollama_event(
                "[async] Image content detected. Adding to stream payload.",
                level="info",
            )
            user_message["images"] = [image]

        messages.append(user_message)

        _log_ollama_event(
            f"[async] Prepared contents. Prompt length: {len(prompt)} chars.",
            level="info",
        )

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        if tools:
            _log_ollama_event(
                f"[async] Attaching {len(tools)} tools to streaming request.",
                level="info",
            )
            kwargs["tools"] = tools

        stream = await aclient.chat(**kwargs)

        _log_ollama_event(
            "[async] Stream connection established.", level="success"
        )

        total_chunks = 0
        total_chars = 0

        async for chunk in stream:
            total_chunks += 1

            if not chunk:
                _log_ollama_event(
                    f"[async] Received empty chunk at index {total_chunks}.",
                    level="warning",
                )
                continue

            text = getattr(getattr(chunk, "message", None), "content", None)

            if not text:
                _log_ollama_event(
                    f"[async] Chunk {total_chunks} contained no text.",
                    level="warning",
                )
                continue

            total_chars += len(text)

            _log_ollama_event(
                f"[async] Streaming chunk {total_chunks} ({len(text)} chars).",
                level="info",
            )

            yield text

        _log_ollama_event(
            "[async] Streaming completed successfully. "
            f"Total chunks: {total_chunks}, Total characters: {total_chars}.",
            level="success",
        )

    except Exception as e:
        _log_ollama_event(
            f"[async] Streaming failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


# ---------------------------------------------------------------------------
# Tool / function calling
# ---------------------------------------------------------------------------


async def asyncGenerateWithTools(
    prompt: str,
    system: str,
    model: str,
    aclient: AsyncClient,
    tools: List[Any],
    options: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    ## Description

    Asynchronous helper for tool/function calling with Ollama. Sends the
    prompt along with tool definitions and returns the raw response so the
    caller can inspect `response.message.tool_calls` and orchestrate
    further rounds.

    ## Parameters

    - `prompt` (`str`)
      - Description: The input instruction string for the model.
      - Constraints: Valid user input.
      - Example: "What is the temperature in New York?"

    - `system` (`str`)
      - Description: Core system directive to guide interpretation.
      - Constraints: None.
      - Example: "You are a helpful assistant."

    - `model` (`str`)
      - Description: Identifier of the Ollama model.
      - Constraints: Must be a locally available model that supports tools.
      - Example: "qwen2.5-coder:latest"

    - `aclient` (`AsyncClient`)
      - Description: Asynchronous Ollama client instance.
      - Constraints: Valid `AsyncClient()` structure.
      - Example: `AsyncClient()`

    - `tools` (`List[Any]`)
      - Description: Ordered sequence of callable functions or JSON schema
        tool definitions for the model.
      - Constraints: Valid schema conforming to Ollama's tool expectations.
        The Python SDK auto-parses callables into tool schemas.
      - Example: `[get_temperature]`

    ## Returns

    `Any`

    Structure:

    ```python
    # Raw response object with:
    # response.message.content  -> text reply (may be empty if tool_calls present)
    # response.message.tool_calls -> list of tool call objects
    ollama.ChatResponse
    ```

    ## Raises

    - `Exception`
      - Any error derived from tool configurations or connection timeouts.

    ## Side Effects

    - Injects tool definitions into the Ollama chat request.

    ## Debug Notes

    - Check whether `response.message.tool_calls` is populated.
    - Ensure tool functions have proper docstrings — the Ollama Python SDK
      auto-parses them into tool schemas.

    ## Customization

    For multi-turn tool loops, wrap this function in a `while` loop that
    appends tool results back to the messages.
    """
    _log_ollama_event(
        f"[async][tools] Generating with tools using model: {model}"
    )

    try:
        messages: List[Dict[str, Any]] = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        _log_ollama_event(
            f"[async][tools] Attaching {len(tools)} tools to request.",
            level="info",
        )

        response = await aclient.chat(
            model=model,
            messages=messages,
            tools=tools,
            stream=False,
            options=options,
        )

        has_tool_calls = bool(
            getattr(getattr(response, "message", None), "tool_calls", None)
        )
        _log_ollama_event(
            f"[async][tools] Tool call generation completed. "
            f"tool_calls={has_tool_calls}.",
            level="success",
        )

        return response

    except Exception as e:
        _log_ollama_event(
            f"[async][tools] Tool-assisted generation failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


# ---------------------------------------------------------------------------
# Vision / image understanding
# ---------------------------------------------------------------------------


async def understandImageWithoutSaving(
    image_path: str,
    prompt: str,
    system: str,
    model: str,
    aclient: AsyncClient,
    options: Optional[Dict[str, Any]] = None,
) -> str:
    """
    ## Description

    Analyzes a single image via an Ollama vision model without persisting
    any output to storage. The image path is passed directly to the Ollama
    SDK which handles loading and encoding.

    ## Parameters

    - `image_path` (`str`)
      - Description: Local filesystem path to the image file.
      - Constraints: Must be a valid path to a readable image.
      - Example: "/tmp/snapshot.jpeg"

    - `prompt` (`str`)
      - Description: Instruction pertaining to the image analysis.
      - Constraints: Valid non-empty string.
      - Example: "Describe what you see in this image."

    - `system` (`str`)
      - Description: System instructions constraining the vision response.
      - Constraints: None.
      - Example: "Respond with JSON containing a 'description' field."

    - `model` (`str`)
      - Description: Vision-capable Ollama model identifier.
      - Constraints: Must be a model that supports image inputs.
      - Example: "granite3.2-vision:latest"

    - `aclient` (`AsyncClient`)
      - Description: Async Ollama client instance.
      - Constraints: Valid and initialized.
      - Example: `AsyncClient()`

    ## Returns

    `str`

    Structure:

    ```json
    "{ \"description\": \"Three people walking across the street.\" }"
    ```

    ## Raises

    - `ValueError`
      - If the model returns an empty response.
    - `Exception`
      - File not found, connection errors, or model errors.

    ## Side Effects

    - Logs image loading and analysis progress.

    ## Debug Notes

    - Verify the model supports vision (`granite3.2-vision`, `gemma3`,
      `minicpm-v`, `qwen3-vl`, etc.).
    - Check the image path is accessible and the file is not corrupted.

    ## Customization

    Pass a structured `format` (JSON schema) to `aclient.chat()` for
    deterministic output structure.
    """
    _log_ollama_event(f"Starting image understanding with model: {model}")

    try:
        image_file = Path(image_path)
        if not image_file.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        _log_ollama_event(
            f"Image path resolved: {image_path} "
            f"({image_file.stat().st_size} bytes).",
            level="info",
        )

        # ── Capability guard ───────────────────────────────────────────────
        caps = await checkModelCapabilities(aclient, model)
        if not caps["vision"]:
            raise ValueError(
                f"Model '{model}' does not support vision. "
                f"Detected capabilities: {caps['raw_capabilities']}"
            )

        messages: List[Dict[str, Any]] = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({
            "role": "user",
            "content": prompt,
            "images": [image_path],
        })

        response = await aclient.chat(
            model=model,
            messages=messages,
            stream=False,
            format=getOllamaImageUnderstandingSchema(),
            options=options,
        )

        _log_ollama_event(
            "Model processed image successfully.", level="success"
        )

        text = getattr(getattr(response, "message", None), "content", None)

        if not text:
            _log_ollama_event(
                "Image understanding response is empty.",
                level="error",
                urgency="moderate",
            )
            raise ValueError("Empty response from image understanding.")

        result_text = str(text).strip()

        _log_ollama_event(
            f"Generated description length: {len(result_text)} chars.",
            level="info",
        )

        return result_text

    except Exception as e:
        _log_ollama_event(
            f"Image understanding failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


async def understandImagesWithoutSaving(
    image_paths: list[str],
    prompt: str,
    system: str,
    model: str,
    aclient: AsyncClient,
    options: Optional[Dict[str, Any]] = None,
) -> str:
    """
    ## Description

    Performs multi-image understanding using a specified Ollama vision model
    without persisting files to storage. All image paths are passed in a
    single message via the `images` key.

    ## Parameters

    - `image_paths` (`list[str]`)
      - Description: Array of local filesystem paths to images for analysis.
      - Constraints: Each element must be a valid file path. At least one required.
      - Example: `["/tmp/seq1.jpeg", "/tmp/seq2.jpeg"]`

    - `prompt` (`str`)
      - Description: Query string for aggregated analysis over the images.
      - Constraints: Clear instruction string.
      - Example: "Describe how the sky color changes over these two frames."

    - `system` (`str`)
      - Description: System template for constraining the generation.
      - Constraints: None explicitly.
      - Example: "Be precise and analytical."

    - `model` (`str`)
      - Description: Ollama model capable of multi-image inspection.
      - Constraints: Must support vision with multiple images.
      - Example: "granite3.2-vision:latest"

    - `aclient` (`AsyncClient`)
      - Description: Async Ollama client instance.
      - Constraints: Authenticated and initialized.
      - Example: `AsyncClient()`

    ## Returns

    `str`

    Structure:

    ```json
    "{ \"description\": \"The sky darkens from frame 1 to frame 2.\" }"
    ```

    ## Raises

    - `ValueError`
      - When an empty `image_paths` array is given or empty response received.
    - `Exception`
      - File I/O errors or connection failures.

    ## Side Effects

    - Validates each image path exists before sending.

    ## Debug Notes

    - Multi-image support depends on the model. Some models only support
      single images.
    - Check image ordering as it affects the model's interpretation.

    ## Customization

    Pass a custom `format` schema to the chat call for structured output.
    """
    _log_ollama_event(
        f"Starting multi-image understanding with model: {model}"
    )

    try:
        if not image_paths:
            raise ValueError("At least one image path must be provided.")

        # ── Capability guard ───────────────────────────────────────────────
        caps = await checkModelCapabilities(aclient, model)
        if not caps["vision"]:
            raise ValueError(
                f"Model '{model}' does not support vision. "
                f"Detected capabilities: {caps['raw_capabilities']}"
            )

        valid_paths: list[str] = []
        for idx, img_path in enumerate(image_paths):
            p = Path(img_path)
            if not p.exists():
                _log_ollama_event(
                    f"Image {idx + 1} not found: {img_path}",
                    level="error",
                    urgency="moderate",
                )
                raise FileNotFoundError(f"Image not found: {img_path}")

            _log_ollama_event(
                f"Loaded image {idx + 1}/{len(image_paths)} from '{img_path}' "
                f"({p.stat().st_size} bytes).",
                level="info",
            )
            valid_paths.append(img_path)

        messages: List[Dict[str, Any]] = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({
            "role": "user",
            "content": prompt,
            "images": valid_paths,
        })

        response = await aclient.chat(
            model=model,
            messages=messages,
            stream=False,
            format=getOllamaImageUnderstandingSchema(),
            options=options,
        )

        _log_ollama_event(
            "Model processed multi-image request successfully.",
            level="success",
        )

        text = getattr(getattr(response, "message", None), "content", None)

        if not text:
            _log_ollama_event(
                "Multi-image understanding response is empty.",
                level="error",
                urgency="moderate",
            )
            raise ValueError("Empty response from multi-image understanding.")

        result_text = str(text).strip()

        _log_ollama_event(
            f"Generated multi-image description length: {len(result_text)} chars.",
            level="info",
        )

        return result_text

    except Exception as e:
        _log_ollama_event(
            f"Multi-image understanding failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


# ---------------------------------------------------------------------------
# JSON helper
# ---------------------------------------------------------------------------


def _safe_json_loads(raw: Any) -> Optional[Dict[str, Any]]:
    """
    ## Description

    Internal helper performing best-effort JSON extraction over unpredictable
    payloads. Normalizes returns from dictionaries to bare strings smoothly.

    ## Parameters

    - `raw` (`Any`)
      - Description: Target variable, usually the model response text.
      - Constraints: Usually a dictionary, string, or None.
      - Example: "{ \"status\": \"success\" }"

    ## Returns

    `Optional[Dict[str, Any]]`

    Structure:

    ```json
    {
        "status": "success",
        "nested": {"id": 1}
    }
    ```

    ## Raises

    - `Exception`
      - Typically swallowed cleanly returning `None`.

    ## Side Effects

    - Strips whitespace from strings before parsing.

    ## Debug Notes

    - Yields `None` whenever JSON parsing fails; downstream routines must
      check and accommodate.

    ## Customization

    None
    """
    if raw is None:
        return None

    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return None
        try:
            return json.loads(stripped)
        except Exception:
            return None

    return None


# ---------------------------------------------------------------------------
# Planning helpers
# ---------------------------------------------------------------------------


async def planner(
    model: str,
    system_prompt: str,
    user_prompt: str,
    personality: str,
    additional_prompt: str,
    response_json_schema: Dict[str, Any],
    aclient: AsyncClient,
    iterations: int = 3,
    options: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    ## Description

    Iterative, streaming planner for in-depth research. Repeatedly prompts
    the model to refine a strategy plan, outputting strict JSON updates
    per iteration.

    ## Parameters

    - `model` (`str`)
      - Description: Ollama model identifier for the planning task.
      - Constraints: Must be a locally available model.
      - Example: "gemma3:4b"

    - `system_prompt` (`str`)
      - Description: Baseline system directive controlling planning behavior.
      - Constraints: Contextual string.
      - Example: "You are an expert researcher."

    - `user_prompt` (`str`)
      - Description: The user's research request.
      - Constraints: Must be specific.
      - Example: "Plan an architecture for a neural network."

    - `personality` (`str`)
      - Description: Personality/style string from your config.
      - Constraints: Context string.
      - Example: "Strictly analytical."

    - `additional_prompt` (`str`)
      - Description: Supplemental directives injected during context build.
      - Constraints: Optional addenda.
      - Example: "Account for missing dependencies."

    - `response_json_schema` (`Dict[str, Any]`)
      - Description: JSON schema dict guiding the model's output structure.
      - Constraints: Properly formatted JSON schema.
      - Example: `{"type": "object", "properties": {"steps": {"type": "array"}}}`

    - `aclient` (`AsyncClient`)
      - Description: Async Ollama client instance.
      - Constraints: Valid `AsyncClient()`.
      - Example: `AsyncClient()`

    - `iterations` (`int`, optional)
      - Description: Number of refinement rounds.
      - Constraints: Value >= 1.
      - Default: 3
      - Example: 5

    ## Returns

    `AsyncGenerator[Dict[str, Any], None]`

    Structure:

    ```json
    {
        "iteration": 1,
        "status": "ok",
        "plan": {}
    }
    ```

    ## Raises

    - `ValueError`
      - When underlying generation yields empty text.
    - `Exception`
      - Any execution faults from the generation engine.

    ## Side Effects

    - Synthesis of constraints dynamically per iteration.
    - Captures previous plan state for iterative refinement.

    ## Debug Notes

    - Verify iterations minimum constraint (`iterations < 1` is clamped to 1).
    - Error yields produce JSON blocks with `status="error"` for safe UI handling.

    ## Customization

    The system prompt assembly can accept additional formatting constraints.
    """
    _log_ollama_event(
        f"[async][planner] Starting planner stream (iterations={iterations}) model={model}",
        level="info",
    )

    if iterations < 1:
        _log_ollama_event(
            "[async][planner] iterations < 1; forcing iterations=1",
            level="warning",
        )
        iterations = 1

    system = "\n\n".join(
        [
            system_prompt.strip(),
            "PERSONALITY:\n" + (personality or "").strip(),
            "ADDITIONAL CONSTRAINTS:\n" + (additional_prompt or "").strip(),
            "PLANNER RULES:\n"
            "- Output MUST match the provided JSON schema.\n"
            "- Be specific, actionable, and research-oriented.\n"
            "- Prefer fewer, clearer steps over many vague steps.\n"
            "- Include verification steps and sources strategy when relevant.\n"
            "- Avoid repeating the JSON schema or adding markdown fences.\n",
        ]
    ).strip()

    previous_plan_raw: Optional[str] = None

    for i in range(iterations):
        iteration_no = i + 1

        if previous_plan_raw:
            prompt = (
                "You are iteratively refining a research plan.\n\n"
                "USER REQUEST:\n"
                f"{user_prompt}\n\n"
                "CURRENT PLAN (JSON):\n"
                f"{previous_plan_raw}\n\n"
                "TASK:\n"
                "- Improve the plan for depth and clarity.\n"
                "- Fix missing steps, weak ordering, missing assumptions, or missing validation.\n"
                "- Keep the overall structure stable; only change what improves quality.\n"
                "- Return the FULL updated plan as JSON.\n"
            )
        else:
            prompt = (
                "Create a plan for conducting in-depth research.\n\n"
                "USER REQUEST:\n"
                f"{user_prompt}\n\n"
                "TASK:\n"
                "- Produce a step-by-step plan suitable for a research agent.\n"
                "- Return JSON only, matching the provided schema.\n"
            )

        _log_ollama_event(
            f"[async][planner] Iteration {iteration_no}/{iterations} request started.",
            level="info",
        )

        response_text = await asyncGenerateContent(
            prompt=prompt,
            system=system,
            model=model,
            image=None,
            aclient=aclient,
            tools=None,
            json_schema=response_json_schema,
            options=options,
        )

        parsed = _safe_json_loads(response_text)
        if parsed is None:
            _log_ollama_event(
                f"[async][planner] Iteration {iteration_no} returned non-JSON or empty output.",
                level="error",
                urgency="critical",
            )
            yield {
                "iteration": iteration_no,
                "status": "error",
                "error": "Planner returned invalid JSON.",
                "raw": response_text,
            }
            previous_plan_raw = response_text
            continue

        parsed = dict(parsed)
        parsed.setdefault("iteration", iteration_no)
        parsed.setdefault("status", "ok")

        _log_ollama_event(
            f"[async][planner] Iteration {iteration_no} plan generated successfully.",
            level="success",
        )

        yield parsed
        previous_plan_raw = response_text

    _log_ollama_event(
        "[async][planner] Planner stream completed.",
        level="success",
    )


async def updatePlan(
    model: str,
    system_prompt: str,
    new_user_request: str,
    existing_plan_json: Any,
    relevant_context: str,
    personality: str,
    additional_prompt: str,
    response_json_schema: Dict[str, Any],
    aclient: AsyncClient,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    ## Description

    Updates an existing research plan minimally based on a new user request.
    Instructs the model to change only impacted steps and preserve the rest.

    ## Parameters

    - `model` (`str`)
      - Description: Ollama model for the update task.
      - Constraints: Valid locally available model.
      - Example: "gemma3:4b"

    - `system_prompt` (`str`)
      - Description: Global constraints shaping operational focus.
      - Constraints: Baseline template string.
      - Example: "Be precise."

    - `new_user_request` (`str`)
      - Description: The new directive from the user.
      - Constraints: String query.
      - Example: "Also integrate a caching layer."

    - `existing_plan_json` (`Any`)
      - Description: Raw object or JSON string of the initial plan.
      - Constraints: Needs parsing compatibility.
      - Example: `{"status": "ok", "steps": []}`

    - `relevant_context` (`str`)
      - Description: Aggregated context constraining the update.
      - Constraints: Meaningful string.
      - Example: "App is being built for high concurrency."

    - `personality` (`str`)
      - Description: Output tonal or stylistic profile.
      - Constraints: Standard string.
      - Example: "Formal."

    - `additional_prompt` (`str`)
      - Description: Extra directives injected below primary config.
      - Constraints: Optional addenda.
      - Example: "Ensure no steps are dropped."

    - `response_json_schema` (`Dict[str, Any]`)
      - Description: Expected JSON schema for the updated plan.
      - Constraints: Dict object schema.
      - Example: `{"type": "object"}`

    - `aclient` (`AsyncClient`)
      - Description: Async Ollama client instance.
      - Constraints: Valid `AsyncClient()`.
      - Example: `AsyncClient()`

    ## Returns

    `Dict[str, Any]`

    Structure:

    ```json
    {
        "status": "ok",
        "updated_steps": []
    }
    ```

    ## Raises

    - `ValueError`
      - When generated content validation fails.
    - `Exception`
      - Any connection or model error.

    ## Side Effects

    - Dynamically compiles system and prompt strings for the update request.

    ## Debug Notes

    - Captures fail states cleanly by returning an error envelope dict
      instead of crashing if JSON parsing fails.

    ## Customization

    Update the prompt template strings to adjust how the model interprets
    update instructions.
    """
    _log_ollama_event(
        f"[async][plan-update] Starting plan update model={model}",
        level="info",
    )

    existing_plan_dict = _safe_json_loads(existing_plan_json) or (
        existing_plan_json if isinstance(existing_plan_json, dict) else None
    )
    existing_plan_raw = (
        json.dumps(existing_plan_dict, ensure_ascii=False)
        if existing_plan_dict is not None
        else str(existing_plan_json)
    )

    system = "\n\n".join(
        [
            system_prompt.strip(),
            "PERSONALITY:\n" + (personality or "").strip(),
            "ADDITIONAL CONSTRAINTS:\n" + (additional_prompt or "").strip(),
            "PLAN UPDATE RULES:\n"
            "- Output MUST match the provided JSON schema.\n"
            "- Make the smallest possible edit set.\n"
            "- Do NOT rewrite unaffected steps.\n"
            "- Keep naming/formatting stable.\n"
            "- Return the FULL updated plan as JSON.\n",
        ]
    ).strip()

    prompt = (
        "You are updating an existing research plan.\n\n"
        "RELEVANT CONTEXT:\n"
        f"{relevant_context}\n\n"
        "NEW USER REQUEST:\n"
        f"{new_user_request}\n\n"
        "EXISTING PLAN (JSON):\n"
        f"{existing_plan_raw}\n\n"
        "TASK:\n"
        "- Identify which steps are impacted by the new request.\n"
        "- Update ONLY those steps (and any necessary dependencies).\n"
        "- Keep all other steps unchanged.\n"
        "- Return the FULL updated plan as JSON.\n"
    )

    _log_ollama_event(
        "[async][plan-update] Sending update request to model.",
        level="info",
    )

    response_text = await asyncGenerateContent(
        prompt=prompt,
        system=system,
        model=model,
        image=None,
        aclient=aclient,
        tools=None,
        json_schema=response_json_schema,
        options=options,
    )

    parsed = _safe_json_loads(response_text)
    if parsed is None:
        _log_ollama_event(
            "[async][plan-update] Model returned invalid JSON for updated plan.",
            level="error",
            urgency="critical",
        )
        return {
            "status": "error",
            "error": "Plan update returned invalid JSON.",
            "raw": response_text,
        }

    _log_ollama_event(
        "[async][plan-update] Plan updated successfully.",
        level="success",
    )
    parsed = dict(parsed)
    parsed.setdefault("status", "ok")
    return parsed

"""
## Description

The `DRGeminiWrapper` module provides synchronous and asynchronous interfaces to interact with Google's Gemini models. It abstracts the boilerplate code related to initializing the clients, managing API keys securely, executing generative model calls, handling multi-modal vision tasks, iterating through AI-directed plans, and enforcing strict JSON output structures. All events are logged uniformly to the central DRLogger.

## Parameters

None (Module Level)

## Returns

None (Module Level)

## Raises

- `ValueError`
  - When required dependencies, such as the Gemini API key, are absent.
- `Exception`
  - Wraps generic or unhandled issues from the upstream Google SDK.

## Side Effects

- Reads API keys securely from `DRSecrets`.
- Logs extensive metadata and model invocation tracking to the system logger.
- Can create temporary payloads from loaded images into memory buffers during interactions.

## Debug Notes

- Monitor the `SECRETS_MANAGEMENT` tag in logs for client initialization errors.
- Async variants expect `.aio` compatible clients.

## Customization

You can change global constants `LOG_SOURCE` or `LOG_TAGS` to route generation logs differently.
"""


from google.genai import Client, types
from google.genai.types import ContentListUnionDict
from google.genai.types import Model
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    Generator,
    List,
    Literal,
    Optional,
)
from PIL import Image
import json
from main.src.utils.versionManagement import getAppVersion
from main.src.utils.llms.prompts.getSchema import getImageUnderstandingSchema
from main.src.utils.DRLogger import dr_logger
from main.secrets.DRSecrets import Secrets


LOG_SOURCE = "system"
LOG_TAGS = ["SECRETS_MANAGEMENT"]


def _log_googleai_event(
    message: str,
    level: Literal["success", "error", "warning", "info"] = "info",
    urgency: Literal["none", "moderate", "critical"] = "none",
):
    """
    ## Description

    Internal utility function for logging secret management events with structured
    metadata. Ensures all secret-related operations are tracked with appropriate
    urgency levels and log sources.

    ## Parameters

    - `level` (`Literal["success", "error", "warning", "info"]`)
      - Description: Log severity level indicating the nature of the event.
      - Constraints: Must be one of: "success", "error", "warning", "info".
      - Example: "error"

    - `message` (`str`)
      - Description: Human-readable description of the secret event.
      - Constraints: Must be non-empty. Should not contain sensitive data (API keys, tokens).
      - Example: ".env file not found at /path/to/.env"

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
    - Tags all events with "SECRETS_MANAGEMENT" for filtering.

    ## Debug Notes

    - Ensure messages do NOT contain sensitive information (API keys, tokens).
    - Use appropriate urgency levels: "critical" for missing keys, "moderate" for fallbacks.
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
        app_version=getAppVersion(),
    )


def getClient():
    """
    ## Description

    Initializes and returns the synchronous Gemini API client.
    Retrieves the necessary API key from the secret manager.

    ## Parameters

    None

    ## Returns

    `Client`

    Structure:

    ```python
    google.genai.Client
    ```

    ## Raises

    - `ValueError`
      - When the Gemini API key is missing or initialization fails.

    ## Side Effects

    - Logs initialization attempts and successes to the DRLogger system.
    - Reads secrets from the environment.

    ## Debug Notes

    - Verify that the Gemini API key is correctly configured in the secret manager.
    - Check application logs if initialization fails.

    ## Customization

    None
    """
    _log_googleai_event("Initializing Gemini Client")
    secrets = Secrets()
    api_key = secrets.get_gemini_api_key()
    if not api_key:
        _log_googleai_event(
            "Gemini API key is missing.", level="error", urgency="critical"
        )
        raise ValueError("Gemini API key is missing.")
    try:
        _log_googleai_event("Attempt to create Gemini Client.")
        client = Client(api_key=api_key)
        _log_googleai_event("Gemini Client initialized successfully.", level="success")
    except ValueError as e:
        _log_googleai_event(str(e), level="error", urgency="critical")
        raise
    return client


def getAsyncClient():
    """
    ## Description

    Initializes and returns the asynchronous Gemini client.
    Provides the `.aio` interface for high-concurrency workloads.

    ## Parameters

    None

    ## Returns

    `Any`

    Structure:

    ```python
    google.genai.Client().aio
    ```

    ## Raises

    - `ValueError`
      - When the Gemini API key is missing or initialization fails.

    ## Side Effects

    - Logs the initialization process using the DRLogger system.
    - Reads the API key from the secret manager.

    ## Debug Notes

    - Verify `.env` or secret configuration for `GEMINI_API_KEY`.
    - Check the logs for critical errors during instancing.

    ## Customization

    None
    """
    _log_googleai_event("Initializing async Gemini Client")
    secrets = Secrets()
    api_key = secrets.get_gemini_api_key()
    if not api_key:
        _log_googleai_event(
            "Gemini API key is missing for async client.",
            level="error",
            urgency="critical",
        )
        raise ValueError("Gemini API key is missing.")

    try:
        _log_googleai_event("Attempt to create async Gemini Client.")
        client = Client(api_key=api_key).aio
        _log_googleai_event(
            "Async Gemini Client initialized successfully.", level="success"
        )
    except ValueError as e:
        _log_googleai_event(str(e), level="error", urgency="critical")
        raise

    return client


def getModelList(client: Client) -> list[dict]:
    """
    ## Description

    Retrieves a list of all available Gemini models using the provided client.
    Parses the model objects into standard Python dictionaries.

    ## Parameters

    - `client` (`Client`)
      - Description: The synchronous Gemini API client instance.
      - Constraints: Must be properly initialized and authenticated.
      - Example: `Client()`

    ## Returns

    `list[dict]`

    Structure:

    ```json
    [
        {
            "name": "models/gemini-3.1-pro",
            "version": "3.1",
            "display_name": "Gemini 3.1 Pro"
        }
    ]
    ```

    ## Raises

    - `Exception`
      - When the model retrieval API call fails.

    ## Side Effects

    - Logs the retrieval attempt, success count, or failure details.

    ## Debug Notes

    - Validate the client instance if exceptions are thrown.
    - Uses Pydantic's model dumping with a fallback to `__dict__`.

    ## Customization

    None
    """
    _log_googleai_event("Retrieving list of available Gemini models.")

    try:
        model_list = client.models.list()

        parsed_models = []

        for model in model_list:
            try:
                model_dict = model.model_dump()  # modern pydantic way
            except AttributeError:
                model_dict = model.__dict__  # fallback safety

            parsed_models.append(model_dict)

        _log_googleai_event(
            f"Retrieved {len(parsed_models)} models successfully.",
            level="success",
        )

        return parsed_models

    except Exception as e:
        _log_googleai_event(
            str(e),
            level="error",
            urgency="critical",
        )
        raise


def getGeminiModel(client: Client, model_name: str = "gemini-3.1-pro") -> Model:
    """
    ## Description

    Retrieves a specific Gemini model by its name using the provided client object.

    ## Parameters

    - `client` (`Client`)
      - Description: The initialized synchronous Gemini API client instance.
      - Constraints: Must be valid and authenticated.
      - Example: `Client()`

    - `model_name` (`str`)
      - Description: The specific model identifier to fetch.
      - Constraints: Must be a valid Google generative AI model name.
      - Example: "gemini-3.1-pro"

    ## Returns

    `Model`

    Structure:

    ```python
    google.genai.types.Model
    ```

    ## Raises

    - `ValueError`
      - If the specified model name is invalid or not available.

    ## Side Effects

    - Logs the specific model fetch attempt and its resolution.

    ## Debug Notes

    - Check logs if the fallback names are incorrect or if access is denied.
    - Validate model spelling if a ValueError surfaces.

    ## Customization

    Change the default `model_name` parameter to default to another variant.
    """
    _log_googleai_event(f"Retrieving Gemini model: {model_name}")
    try:
        model = client.models.get(model=model_name)
        _log_googleai_event(
            f"Gemini model '{model_name}' retrieved successfully.", level="success"
        )
        return model
    except ValueError as e:
        _log_googleai_event(str(e), level="error", urgency="critical")
        raise


def generateContent(
    prompt: str,
    system: str,
    model: str,
    image: Optional[str],
    client: Client,
) -> str:
    """
    ## Description

    Generates text content synchronously using a specified Gemini model, prompt, and optional image.

    ## Parameters

    - `prompt` (`str`)
      - Description: The primary input instruction or text query for the LLM.
      - Constraints: Must be non-empty.
      - Example: "What is the capital of France?"

    - `system` (`str`)
      - Description: System-level instructions to steer the model's behavior and constraints.
      - Constraints: Can be empty, but conventionally structures response traits.
      - Example: "You are a helpful geography expert."

    - `model` (`str`)
      - Description: The identifier of the chosen Gemini model.
      - Constraints: Must be a valid model name.
      - Example: "gemini-3.1-pro"

    - `image` (`Optional[str]`)
      - Description: URL, byte data, or path for the image being processed. Optional.
      - Constraints: If provided, must be formatted correctly for the API.
      - Example: None

    - `client` (`Client`)
      - Description: The authenticated Gemini client.
      - Constraints: Must be valid and authenticated.
      - Example: `Client()`

    ## Returns

    `str`

    Structure:

    ```json
    "Paris is the capital of France."
    ```

    ## Raises

    - `ValueError`
      - When the generated content's `text` property is empty or None.
    - `Exception`
      - When the generation API request fails or network drops.

    ## Side Effects

    - Logs the generation process and character output length.

    ## Debug Notes

    - If getting empty string errors, check model generation limits or prompt safety blockages.
    - Verify image bytes/path parsing if image injection fails.

    ## Customization

    Modify the `contents` list order if prompt/image relation needs specific structure depending on LLM parsing.
    """
    _log_googleai_event(f"Generating content with model: {model}")

    try:
        contents = []

        if image:
            contents.append(image)

        contents.append(prompt)

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system),
        )

        _log_googleai_event("Content generated successfully.", level="success")

        if not response or not getattr(response, "text", None):
            _log_googleai_event(
                "Generated content is empty.",
                level="error",
                urgency="moderate",
            )
            raise ValueError("Generated content is empty.")

        return str(response.text).strip()

    except Exception as e:
        _log_googleai_event(
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
) -> Generator[str, None, None]:
    """
    ## Description

    Generates content iteratively via response streaming, yielding chunks of text 
    as they are processed by the specified Gemini model.

    ## Parameters

    - `prompt` (`str`)
      - Description: Primary text prompt for the conversational iteration.
      - Constraints: Must be a valid standard string.
      - Example: "Write a long story about spaceships."

    - `system` (`str`)
      - Description: Guiding system instructions for the LLM personality and output format.
      - Constraints: None.
      - Example: "Respond strictly in markdown."

    - `model` (`str`)
      - Description: The generative model identifier.
      - Constraints: Must be a valid model string such as `gemini-3.1-pro`.
      - Example: "gemini-3.1-pro"

    - `image` (`Optional[str]`)
      - Description: Image data or payload context. Optional.
      - Constraints: Handled appropriately by downstream clients.
      - Example: None

    - `client` (`Client`)
      - Description: The authenticated synchronous GenAI client.
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
      - Raised if the stream unexpectedly breaks or the initial connection fails.

    ## Side Effects

    - Streams logs reflecting chunk counts and total streaming size.

    ## Debug Notes

    - Empty chunks are skipped and logged. Monitor the warnings if output appears choppy.
    - Watch for API rate limits given the longer duration of stream connections.

    ## Customization

    Add additional modalities inside the `contents` array if needed.
    """
    _log_googleai_event(f"Starting streaming generation with model: {model}")

    try:
        contents = []

        if image:
            _log_googleai_event("Image content detected. Adding to stream payload.")
            contents.append(image)

        contents.append(prompt)

        _log_googleai_event(
            f"Prepared contents. Prompt length: {len(prompt)} chars.",
            level="info",
        )

        stream = client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system),
        )

        _log_googleai_event("Stream connection established.", level="success")

        total_chunks = 0
        total_chars = 0

        for chunk in stream:
            total_chunks += 1

            if not chunk:
                _log_googleai_event(
                    f"Received empty chunk at index {total_chunks}.",
                    level="warning",
                )
                continue

            text = getattr(chunk, "text", None)

            if not text:
                _log_googleai_event(
                    f"Chunk {total_chunks} contained no text.",
                    level="warning",
                )
                continue

            total_chars += len(text)

            _log_googleai_event(
                f"Streaming chunk {total_chunks} ({len(text)} chars).",
                level="info",
            )

            yield text

        _log_googleai_event(
            f"Streaming completed successfully. "
            f"Total chunks: {total_chunks}, Total characters: {total_chars}.",
            level="success",
        )

    except Exception as e:
        _log_googleai_event(
            f"Streaming failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


async def asyncGenerateContent(
    prompt: str,
    system: str,
    model: str,
    image: Optional[str],
    aclient: Any,
    tools: Optional[List[Any]] = None,
    json_schema: Optional[Dict[str, Any]] = None,
) -> str:
    """
    ## Description

    Asynchronously generates text content utilizing a Gemini model with optional 
    support for structured tool calling and JSON schema constraints.

    ## Parameters

    - `prompt` (`str`)
      - Description: Main user prompt and request instructions.
      - Constraints: Must be a clear string.
      - Example: "Tell me the weather."

    - `system` (`str`)
      - Description: System-level framing and context constraints.
      - Constraints: None natively, but affects inference.
      - Example: "You are a meteorological assistant."

    - `model` (`str`)
      - Description: Name of the active Gemini model.
      - Constraints: Valid model name string.
      - Example: "gemini-3.1-pro"

    - `image` (`Optional[str]`)
      - Description: Extra context provided through image tokens.
      - Constraints: Expected format depends on `aclient` parsing capability.
      - Example: None

    - `aclient` (`Any`)
      - Description: The `.aio` instantiated asynchronous Gemini client.
      - Constraints: Must support the `.models.generate_content` interface.
      - Example: `Client().aio`

    - `tools` (`Optional[List[Any]]`, optional)
      - Description: Function tools for automated LLM orchestration.
      - Constraints: Must match schema parsing or callable requirements.
      - Default: None
      - Example: `[weather_function]`

    - `json_schema` (`Optional[Dict[str, Any]]`, optional)
      - Description: Forced structured output template for JSON mode.
      - Constraints: Dictionary resembling a standard JSON schema object.
      - Default: None
      - Example: `{"type": "object", "properties": {"temperature": {"type": "number"}}}`

    ## Returns

    `str`

    Structure:

    ```json
    "{ \"temperature\": 22 }"
    ```

    ## Raises

    - `ValueError`
      - If generated content yields an empty string object.
    - `Exception`
      - When asynchronous generation calls encounter network or permission faults.

    ## Side Effects

    - May inject configuration options enabling tools and strict JSON typing.
    - Logs asynchronous events sequentially.

    ## Debug Notes

    - Validate the parameter types of `json_schema` to prevent backend crashes.
    - Tool handling needs proper definition passing or API denies the request.

    ## Customization

    Modify the `config` payload dictionary initialization to incorporate temperature or token caps.
    """
    _log_googleai_event(f"[async] Generating content with model: {model}")

    try:
        contents: List[ContentListUnionDict] = []

        if image:
            _log_googleai_event(
                "[async] Image content detected. Adding to payload.", level="info"
            )
            contents.append(image)

        contents.append(prompt)

        config: Dict[str, Any] = {
            "system_instruction": system,
        }

        if tools:
            _log_googleai_event(
                f"[async] Attaching {len(tools)} tools to request.", level="info"
            )
            config["tools"] = tools

        if json_schema is not None:
            _log_googleai_event(
                "[async] Enabling JSON schema constrained output.", level="info"
            )
            config["response_mime_type"] = "application/json"
            config["response_json_schema"] = json_schema

        response = await aclient.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**config),
        )

        _log_googleai_event(
            "[async] Content generated successfully.", level="success"
        )

        if not response or not getattr(response, "text", None):
            _log_googleai_event(
                "[async] Generated content is empty.",
                level="error",
                urgency="moderate",
            )
            raise ValueError("Generated content is empty.")

        return str(response.text).strip()

    except Exception as e:
        _log_googleai_event(
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
    aclient: Any,
    tools: Optional[List[Any]] = None,
) -> AsyncGenerator[str, None]:
    """
    ## Description

    Asynchronously generates content via streaming from a specified Gemini model.
    Suitable for high-concurrency web handlers returning chunked text back to the client.

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
      - Description: The specific GenAI model identifier.
      - Constraints: String corresponding to a valid GenAI stream-capable model.
      - Example: "gemini-3.1-pro"

    - `image` (`Optional[str]`)
      - Description: Optional base64 or path to an image file.
      - Constraints: Handled via the Gemini client payload if present.
      - Example: None

    - `aclient` (`Any`)
      - Description: Asynchronous instance of the GenAI API client.
      - Constraints: Proper valid async client pointer.
      - Example: `Client().aio`

    - `tools` (`Optional[List[Any]]`, optional)
      - Description: Function tool specifications.
      - Constraints: Valid structure for Gemini tool ingestion.
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
      - If the stream generator fails or the initial network request faults.

    ## Side Effects

    - Outputs incremental log updates highlighting chuck volume and characters per iteration.

    ## Debug Notes

    - The `total_chunks` and `total_chars` variables in logs can diagnose cut-offs or stream drops early.
    - Tool support with async streams requires SDK parsing handlers depending on Google's package version.

    ## Customization

    Further inject stream options (like max tokens) into the dictionary parameter inside this function.
    """
    _log_googleai_event(f"[async] Starting streaming generation with model: {model}")

    try:
        contents: List[ContentListUnionDict] = []

        if image:
            _log_googleai_event(
                "[async] Image content detected. Adding to stream payload.", level="info"
            )
            contents.append(image)

        contents.append(prompt)

        _log_googleai_event(
            f"[async] Prepared contents. Prompt length: {len(prompt)} chars.",
            level="info",
        )

        config: Dict[str, Any] = {
            "system_instruction": system,
        }

        if tools:
            _log_googleai_event(
                f"[async] Attaching {len(tools)} tools to streaming request.",
                level="info",
            )
            config["tools"] = tools

        stream = await aclient.models.generate_content_stream(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**config),
        )

        _log_googleai_event(
            "[async] Stream connection established.", level="success"
        )

        total_chunks = 0
        total_chars = 0

        async for chunk in stream:
            total_chunks += 1

            if not chunk:
                _log_googleai_event(
                    f"[async] Received empty chunk at index {total_chunks}.",
                    level="warning",
                )
                continue

            text = getattr(chunk, "text", None)

            if not text:
                _log_googleai_event(
                    f"[async] Chunk {total_chunks} contained no text.",
                    level="warning",
                )
                continue

            total_chars += len(text)

            _log_googleai_event(
                f"[async] Streaming chunk {total_chunks} ({len(text)} chars).",
                level="info",
            )

            yield text

        _log_googleai_event(
            "[async] Streaming completed successfully. "
            f"Total chunks: {total_chunks}, Total characters: {total_chars}.",
            level="success",
        )

    except Exception as e:
        _log_googleai_event(
            f"[async] Streaming failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


async def asyncGenerateWithTools(
    prompt: str,
    system: str,
    model: str,
    aclient: Any,
    tools: List[Any],
    automatic_mode: Literal["AUTO", "ANY", "NONE"] = "AUTO",
    maximum_remote_calls: int = 10,
) -> Any:
    """
    ## Description

    Orchestrates complex generative workflows utilizing function calling controls.
    Bridges asynchronous responses with either manual tool parsing or auto-invocation logic.

    ## Parameters

    - `prompt` (`str`)
      - Description: The input instruction string for the generative model.
      - Constraints: Valid user input.
      - Example: "How much space does directory /foo take?"

    - `system` (`str`)
      - Description: Core system directive to guide interpretation of the task.
      - Constraints: None.
      - Example: "You are a Linux administrator."

    - `model` (`str`)
      - Description: Identifier of the respective generative model.
      - Constraints: Valid string format.
      - Example: "gemini-3.1-pro"

    - `aclient` (`Any`)
      - Description: Asynchronous Gemini client object wrapper instance.
      - Constraints: Valid `Client().aio` structure.
      - Example: `Client().aio`

    - `tools` (`List[Any]`)
      - Description: Ordered sequence of callable or dictionary tools for the model.
      - Constraints: Valid schema conforming to Google GenAI expectations.
      - Example: `[execute_bash]`

    - `automatic_mode` (`Literal["AUTO", "ANY", "NONE"]`, optional)
      - Description: Setting to control standard API function automation logic.
      - Constraints: Must be "AUTO", "ANY", or "NONE".
      - Default: "AUTO"
      - Example: "ANY"

    - `maximum_remote_calls` (`int`, optional)
      - Description: If in ANY mode, restricts recursive tool invocation ceilings.
      - Constraints: Positive integer bounds.
      - Default: 10
      - Example: 10

    ## Returns

    `Any`

    Structure:

    ```python
    # A Raw response class containing properties such as response.function_calls
    # or response.text dependent on Google GenAI structures.
    google.genai.types.GenerateContentResponse
    ```

    ## Raises

    - `Exception`
      - Any arbitrary error derived from tool configurations or network timeouts.

    ## Side Effects

    - Injects specific tool configuration profiles into the GenAI request structure payload.

    ## Debug Notes

    - Check whether `response.function_calls` contains any mapped structures.
    - When using `automatic_mode="ANY"`, the response typically terminates quickly. Handle carefully.

    ## Customization

    To change automatic execution limits natively, manipulate the default value for `maximum_remote_calls`.
    """
    _log_googleai_event(
        f"[async][tools] Generating with tools (mode={automatic_mode}) using model: {model}"
    )

    try:
        config: Dict[str, Any] = {
            "system_instruction": system,
            "tools": tools,
        }

        if automatic_mode == "AUTO":
            # Default automatic behavior – no additional config required.
            _log_googleai_event(
                "[async][tools] Using default automatic function calling.",
                level="info",
            )
        elif automatic_mode == "ANY":
            _log_googleai_event(
                "[async][tools] Forcing ANY mode; model will always return function calls.",
                level="info",
            )
            config["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=maximum_remote_calls
            )
            config["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )
        elif automatic_mode == "NONE":
            _log_googleai_event(
                "[async][tools] Disabling automatic function calling.",
                level="info",
            )
            config["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                disable=True
            )
        else:
            _log_googleai_event(
                f"[async][tools] Invalid automatic_mode={automatic_mode}; defaulting to AUTO.",
                level="warning",
            )

        response = await aclient.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**config),
        )

        has_functions = bool(getattr(response, "function_calls", None))
        _log_googleai_event(
            f"[async][tools] Tool call generation completed. function_calls={has_functions}.",
            level="success",
        )

        return response

    except Exception as e:
        _log_googleai_event(
            f"[async][tools] Tool-assisted generation failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


def understandImageWithoutSaving(
    image_path: str,
    prompt: str,
    system: str,
    model: str,
    client: Client,
) -> str:
    """
    ## Description

    Analyzes a given image via generating an understanding/description directly, 
    without saving the output context or blob data to a persistent store or bucket.

    ## Parameters

    - `image_path` (`str`)
      - Description: Local storage path pointer to fetch bytes forming the image payload.
      - Constraints: Resolvable absolute or relative path to an applicable image format.
      - Example: "/var/tmp/snapshot.jpeg"

    - `prompt` (`str`)
      - Description: Target questioning or instruction pertaining to the optical analysis.
      - Constraints: Valid non-empty string.
      - Example: "Are there any people in this frame?"

    - `system` (`str`)
      - Description: Guiding structure to constrain or clarify vision context generation.
      - Constraints: None.
      - Example: "Respond strictly with JSON containing a 'description' string."

    - `model` (`str`)
      - Description: Vision-capable generative model identifier.
      - Constraints: GenAI identifier for vision tasks.
      - Example: "gemini-3.1-pro"

    - `client` (`Client`)
      - Description: Instantiated GenAI API client instance pointing to appropriate backend.
      - Constraints: Authorized and active synchronous object.
      - Example: `Client()`

    ## Returns

    `str`

    Structure:

    ```json
    "{ \"description\": \"Three people walking across the street.\" }"
    ```

    ## Raises

    - `ValueError`
      - If the model generation call evaluates or yields to strictly empty content responses.
    - `Exception`
      - Arbitrary file locking, resolving, or request timeout bounds exception.

    ## Side Effects

    - Attempts a file operation reading image data into byte RAM immediately prior to upload context formatting.

    ## Debug Notes

    - Look at byte-size logger output to verify successful retrieval of the uncorrupted file payload.
    - If `getImageUnderstandingSchema` overrides expected models schema mapping, check mapping function compatibility.

    ## Customization

    The `mime_type` inside the `Part.from_bytes()` function defaults currently arbitrarily to `image/jpeg`. Expand using mime types or Pillow format mapping if needed.
    """
    _log_googleai_event(f"Starting image understanding with model: {model}")

    try:
        # --- Read image ---
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        _log_googleai_event(
            f"Image loaded successfully. Size: {len(image_bytes)} bytes.",
            level="info",
        )

        # --- Build request ---
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg",  # change dynamically if needed
                ),
                prompt,
            ],
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "response_json_schema": getImageUnderstandingSchema(),
            },
        )

        _log_googleai_event(
            "Model processed image successfully.",
            level="success",
        )

        if not response or not getattr(response, "text", None):
            _log_googleai_event(
                "Image understanding response is empty.",
                level="error",
                urgency="moderate",
            )
            raise ValueError("Empty response from image understanding.")

        result_text = response.text.strip()

        _log_googleai_event(
            f"Generated description length: {len(result_text)} chars.",
            level="info",
        )

        # ---------------------------------------------------
        # 🔹 PLACEHOLDER: Upload image to storage bucket
        # Example:
        # bucket_url = upload_to_bucket(image_bytes)
        bucket_url = "BUCKET_UPLOAD_PLACEHOLDER"
        # ---------------------------------------------------

        # ---------------------------------------------------
        # 🔹 PLACEHOLDER: Save metadata + AI result to DB
        # Example:
        # save_image_analysis_to_db(
        #     image_path=image_path,
        #     bucket_url=bucket_url,
        #     ai_caption=result_text,
        #     model=model,
        # )
        db_record_id = "DB_SAVE_PLACEHOLDER"
        # ---------------------------------------------------

        _log_googleai_event(
            "Image analysis placeholders executed (DB + Bucket).",
            level="info",
        )

        return result_text

    except Exception as e:
        _log_googleai_event(
            f"Image understanding failed: {e}",
            level="error",
            urgency="critical",
        )
        raise


def understandImagesWithoutSaving(
    image_paths: list[str],
    prompt: str,
    system: str,
    model: str,
    client: Client,
) -> str:
    """
    ## Description

    Performs multi-image understanding using a specified Gemini model without persisting 
    files to long-term database storage. Compiles images into API-accepted payload lists 
    and issues them alongside traditional contextual queries.

    ## Parameters

    - `image_paths` (`list[str]`)
      - Description: Array of physical local paths targeting images to be grouped for analysis.
      - Constraints: Each element must be a valid file target point capable of standard I/O reads.
      - Example: `["/tmp/seq1.jpeg", "/tmp/seq2.jpeg"]`

    - `prompt` (`str`)
      - Description: Query string intended to elicit relational, sequential, or aggregated responses over the images.
      - Constraints: Clear instruction.
      - Example: "Describe how the sky color changes over these two frames."

    - `system` (`str`)
      - Description: Master system template restricting constraints globally for the context generation.
      - Constraints: None explicitly.
      - Example: "Be precise and analytical."

    - `model` (`str`)
      - Description: Gemini model designation capable of multi-image inspection.
      - Constraints: Compatible identifier.
      - Example: "gemini-3.1-pro"

    - `client` (`Client`)
      - Description: Instantiation of the primary GenAI access client hook.
      - Constraints: Authenticated client reference.
      - Example: `Client()`

    ## Returns

    `str`

    Structure:

    ```json
    "{ \"description\": \"The sky darkens from frame 1 to frame 2.\" }"
    ```

    ## Raises

    - `ValueError`
      - When an empty `image_paths` array is given or zero content response is registered natively from Google.
    - `Exception`
      - If local `Pillow` reads, byte-string casting, or global networks sever connection requests.

    ## Side Effects

    - Processes several sequential I/O bytes-read blocks depending on list size configuration constraints.

    ## Debug Notes

    - Multi-modal array chunk ordering heavily impacts generation flow context reading. Note list insertion points.
    - Tracks Pillow extraction logic inside error traps for fallback JPEG mime application properties.

    ## Customization

    Expand the arbitrary standard dictionary response binding inside `types.GenerateContentConfig` using different JSON parsing routines instead.
    """
    _log_googleai_event(
        f"Starting multi-image understanding with model: {model}"
    )

    try:
        if not image_paths:
            raise ValueError("At least one image path must be provided.")

        image_parts: list[ContentListUnionDict] = []

        for idx, image_path in enumerate(image_paths):
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            _log_googleai_event(
                f"Loaded image {idx + 1}/{len(image_paths)} from '{image_path}' "
                f"({len(image_bytes)} bytes).",
                level="info",
            )

            # Try to infer a reasonable MIME type using Pillow; fall back to JPEG.
            try:
                with Image.open(image_path) as img:
                    mime_type = img.get_format_mimetype() or "image/jpeg"
            except Exception:
                mime_type = "image/jpeg"

            image_parts.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                )
            )

        contents: list[ContentListUnionDict] = [
            *image_parts,
            prompt,
        ]

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "response_json_schema": getImageUnderstandingSchema(),
            },
        )

        _log_googleai_event(
            "Model processed multi-image request successfully.",
            level="success",
        )

        if not response or not getattr(response, "text", None):
            _log_googleai_event(
                "Multi-image understanding response is empty.",
                level="error",
                urgency="moderate",
            )
            raise ValueError("Empty response from multi-image understanding.")

        result_text = response.text.strip()

        _log_googleai_event(
            f"Generated multi-image description length: {len(result_text)} chars.",
            level="info",
        )

        return result_text

    except Exception as e:
        _log_googleai_event(
            f"Multi-image understanding failed: {e}",
            level="error",
            urgency="critical",
        )
        raise




# ---------------------------------------------------------------------------
# Artifact generation helpers (e.g., images via Interactions API)
# ---------------------------------------------------------------------------


async def asyncGenerateImageArtifact(
    prompt: str,
    model: str,
    aclient: Any,
) -> Optional[Dict[str, Any]]:
    """
    ## Description

    Generates an image artifact utilizing the asynchronous Interactions API endpoint. 
    Can be used generically to request UI mocks or infographics and parse out image metadata bindings.

    ## Parameters

    - `prompt` (`str`)
      - Description: Detailed natural language description of the target image composition.
      - Constraints: Must be specific and adequately lengthy for accurate image context.
      - Example: "A sleek modern web dashboard mockup in dark mode."

    - `model` (`str`)
      - Description: Image generating Gemini model identifier.
      - Constraints: Valid image GenAI string mapping.
      - Example: "gemini-3.1-pro"

    - `aclient` (`Any`)
      - Description: Async Google client wrapped instance.
      - Constraints: Verified schema integration structure supporting `.interactions`.
      - Example: `Client().aio`

    ## Returns

    `Optional[Dict[str, Any]]`

    Structure:

    ```json
    {
        "mime_type": "image/png",
        "data": "base64_string_data_here"
    }
    ```

    ## Raises

    - `Exception`
      - Encountered if generation server hits errors or the interaction response format unexpectedly changes over the dependency.

    ## Side Effects

    - Initiates network interaction with non-standard Gemini API payload arrays (targeting IMAGE modality).

    ## Debug Notes

    - The Interactions API might return an interaction with no `outputs` list, resulting in a safe `None` return rather than a crash. 
    - Watch for API access permissions on the particular GCP or AI Studio identity.

    ## Customization

    You can append other modalities iteratively inside the `response_modalities` array assignment if audio/video artifacts are later supported.
    """
    _log_googleai_event(
        f"[async][artifact] Creating image artifact with model: {model}."
    )

    try:
        interaction = await aclient.interactions.create(
            model=model,
            input=prompt,
            response_modalities=["IMAGE"],
        )

        image_output = None
        for output in getattr(interaction, "outputs", []) or []:
            if getattr(output, "type", None) == "image":
                image_output = {
                    "mime_type": getattr(output, "mime_type", None),
                    "data": getattr(output, "data", None),
                }
                break

        if not image_output:
            _log_googleai_event(
                "[async][artifact] No IMAGE output found in interaction response.",
                level="warning",
            )
            return None

        _log_googleai_event(
            "[async][artifact] Image artifact generated successfully.",
            level="success",
        )
        return image_output

    except Exception as e:
        _log_googleai_event(
            f"[async][artifact] Failed to generate image artifact: {e}",
            level="error",
            urgency="critical",
        )
        return None


def _safe_json_loads(raw: Any) -> Optional[Dict[str, Any]]:
    """
    ## Description

    Internal helper performing best-effort JSON extraction routines over unpredictable variable payloads.
    Normalizes returns scaling from dictionaries to bare strings smoothly.

    ## Parameters

    - `raw` (`Any`)
      - Description: Target variable, usually the generated content response text payload.
      - Constraints: Usually a dictionary, string, or inherently unassigned.
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
      - Typically swallowed cleanly returning `None`, does not usually raise.

    ## Side Effects

    - Modifies string stripping directly in-memory before yielding the dictionary translation.

    ## Debug Notes

    - Useful for isolating SDK quirks where output mappings fluctuate depending on API beta endpoints.
    - Yields `None` whenever JSON schema breaks entirely; downstream routines must check and accommodate.

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


async def planner(
    model: str,
    system_prompt: str,
    user_prompt: str,
    personality: str,
    additional_prompt: str,
    response_json_schema: Dict[str, Any],
    aclient: Any,
    iterations: int = 3,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    ## Description

    Iterative and streaming planning core for advanced research processing routines.
    Repeatedly prompts the model to refine a strategy plan outputting strict JSON updates per iteration stream block.

    ## Parameters

    - `model` (`str`)
      - Description: GenAI identifier orchestrating the internal planning task.
      - Constraints: Applicable model matching required capabilities.
      - Example: "gemini-3.1-pro"

    - `system_prompt` (`str`)
      - Description: Baseline system directive controlling operational mode and style.
      - Constraints: Contextual string framework constraints.
      - Example: "You are an expert researcher."

    - `user_prompt` (`str`)
      - Description: Task querying objective.
      - Constraints: Specific textual target.
      - Example: "Plan an architecture for a neural-net."

    - `personality` (`str`)
      - Description: Injectable module adjusting response tones systematically.
      - Constraints: Context configurations.
      - Example: "Strictly analytical."

    - `additional_prompt` (`str`)
      - Description: Supplemental user or system directives injected during context build.
      - Constraints: Optional addenda string.
      - Example: "Account for missing dependencies."

    - `response_json_schema` (`Dict[str, Any]`)
      - Description: Dict-mapped structured expected architecture map guiding model generation syntax.
      - Constraints: Properly formatted compliant nested payload.
      - Example: `{"type": "object", "properties": {"steps": {"type": "array"}}}`

    - `aclient` (`Any`)
      - Description: Pointer to the asynchronous execution wrapper client configuration.
      - Constraints: Standard `Client().aio` block structure valid over execution lifetime.
      - Example: `Client().aio`

    - `iterations` (`int`, optional)
      - Description: Upper limit loop controller managing iterative response refinements.
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
      - Underlying generative stream or token generation yields empty text string errors.
    - `Exception`
      - Any execution faults stemming from generation engine bounds limitations.

    ## Side Effects

    - Synthesizes robust constraints dynamically per iteration to push AI logic refinement.
    - Captures previous state frames mapping iteratively into new state payloads incrementally.

    ## Debug Notes

    - Verify iterations minimum logic logic constraint block checks `iterations < 1`.
    - Error yields simulate JSON blocks with `status="error"` avoiding crashes for safe UI mapping.

    ## Customization

    The baseline system prompts logic string assembly can accept additional formatting rule constraints natively.
    """
    _log_googleai_event(
        f"[async][planner] Starting planner stream (iterations={iterations}) model={model}",
        level="info",
    )

    if iterations < 1:
        _log_googleai_event(
            "[async][planner] iterations < 1; forcing iterations=1",
            level="warning",
        )
        iterations = 1

    # Compose a robust base system instruction.
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

        _log_googleai_event(
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
        )

        parsed = _safe_json_loads(response_text)
        if parsed is None:
            _log_googleai_event(
                f"[async][planner] Iteration {iteration_no} returned non-JSON or empty output.",
                level="error",
                urgency="critical",
            )
            # Yield a minimal structured envelope for debugging/UI.
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

        _log_googleai_event(
            f"[async][planner] Iteration {iteration_no} plan generated successfully.",
            level="success",
        )

        yield parsed
        previous_plan_raw = response_text

    _log_googleai_event(
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
    aclient: Any,
) -> Dict[str, Any]:
    """
    ## Description

    Updates an established JSON architecture research plan minimally based on subsequent user directions.
    Instructs the language model to only change specifically impacted schema items.

    ## Parameters

    - `model` (`str`)
      - Description: Relevant target context processing AI model.
      - Constraints: Standard valid GenAI mapping block string.
      - Example: "gemini-3.1-pro"

    - `system_prompt` (`str`)
      - Description: Global constraints shaping internal operational focus.
      - Constraints: Usually pre-mapped baseline templates contexts.
      - Example: "Be precise."

    - `new_user_request` (`str`)
      - Description: Addendum tasks requested following initial build context states.
      - Constraints: String query map.
      - Example: "Also integrate a caching layer."

    - `existing_plan_json` (`Any`)
      - Description: Raw object or translated JSON referencing the initial target plan map.
      - Constraints: Needs parsing compatibilities.
      - Example: `{"status": "ok", "steps": []}`

    - `relevant_context` (`str`)
      - Description: Aggregated surrounding histories, files, or profiling constraints restricting operations.
      - Constraints: Meaningful string injection.
      - Example: "App is being built for high concurrency."

    - `personality` (`str`)
      - Description: Output tonal or stylistic profile alignment map context string.
      - Constraints: Standard string matching logic configurations contexts mappings.
      - Example: "Formal."

    - `additional_prompt` (`str`)
      - Description: Extra directives to inject directly below primary configuration blocks.
      - Constraints: Optional string context limits.
      - Example: "Ensure no steps are dropped."

    - `response_json_schema` (`Dict[str, Any]`)
      - Description: Expected dictionary constraint parsing logic template layout mapping.
      - Constraints: Dict object schema template logic.
      - Example: `{"type": "object"}`

    - `aclient` (`Any`)
      - Description: Async generator GenAI wrapper instance object interface context bindings connection handler.
      - Constraints: `.aio` mapped properties logic bindings mappings.
      - Example: `Client().aio`

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
      - Standard generated content validation failures error logic boundaries target outputs blocks.
    - `Exception`
      - Any arbitrary configuration bounds logic connection logic server target output mapping logic limits variables target target.

    ## Side Effects

    - Manipulates variables dynamically compiling a string context map logic logic parameters payload template block bindings mapping mapping parameter variables logic schemas maps types limits parameters limits structures binding variables limits logic limits logic targets.

    ## Debug Notes

    - Captures fail states cleanly without immediate crashing by appending properties onto valid dictionary variables if logic breaks internally mapping limits.

    ## Customization

    Update explicit variables inside logic constraints template block strings inside function boundaries contexts parameters limits bindings variables mapping object targets boundaries variables.
    """
    _log_googleai_event(
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

    _log_googleai_event(
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
    )

    parsed = _safe_json_loads(response_text)
    if parsed is None:
        _log_googleai_event(
            "[async][plan-update] Model returned invalid JSON for updated plan.",
            level="error",
            urgency="critical",
        )
        return {
            "status": "error",
            "error": "Plan update returned invalid JSON.",
            "raw": response_text,
        }

    _log_googleai_event(
        "[async][plan-update] Plan updated successfully.",
        level="success",
    )
    parsed = dict(parsed)
    parsed.setdefault("status", "ok")
    return parsed

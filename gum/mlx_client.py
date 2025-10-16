"""MLX-based client for vision and text generation tasks.

This module provides a drop-in replacement for OpenAI's API using local MLX models.
It supports both vision tasks (screenshot analysis) and text tasks (proposition generation).
"""

from __future__ import annotations

import asyncio
import base64
import gc
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import mlx.core as mx
from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template


class MLXClient:
    """Client for MLX-based vision and text generation.

    This class provides an interface similar to OpenAI's AsyncOpenAI client,
    but uses local MLX models running on Apple Silicon.

    Args:
        model_name (str): HuggingFace model ID (e.g., "mlx-community/Qwen2-VL-2B-Instruct-4bit")
        max_tokens (int): Maximum tokens to generate. Defaults to 500.
        temperature (float): Sampling temperature. Defaults to 0.7.
        verbose (bool): Enable verbose logging. Defaults to False.
    """

    def __init__(
        self,
        model_name: str = "mlx-community/Qwen2-VL-2B-Instruct-4bit",
        max_tokens: int = 500,
        temperature: float = 0.7,
        verbose: bool = False,
    ):
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.verbose = verbose

        self.logger = logging.getLogger("MLXClient")
        self.model = None
        self.processor = None
        self.config = None

        # Lazy loading - model is loaded on first use
        self._loading_lock = asyncio.Lock()
        self._loaded = False

    async def _ensure_loaded(self):
        """Load the model if not already loaded (thread-safe)."""
        if self._loaded:
            return

        async with self._loading_lock:
            if self._loaded:  # Double-check after acquiring lock
                return

            self.logger.info(f"Loading MLX model: {self.model_name}")

            # Run model loading in thread pool to avoid blocking
            self.model, self.processor = await asyncio.to_thread(
                load, self.model_name
            )
            self.config = self.model.config
            self._loaded = True

            self.logger.info(f"✓ MLX model loaded: {self.model_name}")

    def _encode_image(self, img_path: str) -> str:
        """Encode an image file as base64.

        Args:
            img_path (str): Path to the image file.

        Returns:
            str: Base64 encoded image data.
        """
        with open(img_path, "rb") as fh:
            return base64.b64encode(fh.read()).decode()

    def _extract_image_paths(self, content: List[Dict[str, Any]]) -> List[str]:
        """Extract image paths from OpenAI-style message content.

        Args:
            content (List[Dict]): OpenAI-style content with image_url entries

        Returns:
            List[str]: List of image file paths
        """
        images = []
        for item in content:
            if item.get("type") == "image_url":
                url = item["image_url"]["url"]
                # Handle both base64 data URLs and file paths
                if url.startswith("data:image/"):
                    # Extract base64 data and save temporarily
                    # For now, we'll just skip these - they should be file paths
                    continue
                else:
                    images.append(url)
        return images

    def _extract_text_prompt(self, content: List[Dict[str, Any]]) -> str:
        """Extract text prompt from OpenAI-style message content.

        Args:
            content (List[Dict]): OpenAI-style content with text entries

        Returns:
            str: Combined text prompt
        """
        texts = []
        for item in content:
            if item.get("type") == "text":
                texts.append(item["text"])
        return "\n".join(texts)

    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> "MLXChatCompletion":
        """Create a chat completion (OpenAI-compatible interface).

        Args:
            model (str): Model name (ignored, uses self.model_name)
            messages (List[Dict]): Chat messages in OpenAI format
            response_format (Optional[Dict]): Response format specification
            temperature (Optional[float]): Override default temperature
            max_tokens (Optional[int]): Override default max_tokens

        Returns:
            MLXChatCompletion: Completion result
        """
        await self._ensure_loaded()

        # Extract the user message
        user_msg = None
        for msg in messages:
            if msg["role"] == "user":
                user_msg = msg
                break

        if not user_msg:
            raise ValueError("No user message found")

        content = user_msg["content"]

        # Handle both string and list content
        if isinstance(content, str):
            prompt = content
            images = None
            num_images = 0
        else:
            # Extract images and text from content list
            images = self._extract_image_paths(content)
            prompt = self._extract_text_prompt(content)
            num_images = len(images) if images else 0

        # Add JSON formatting instruction if needed
        if response_format and response_format.get("type") == "json_schema":
            schema = response_format.get("json_schema", {}).get("schema", {})
            prompt = f"{prompt}\n\nPlease respond with a valid JSON object matching this schema:\n{json.dumps(schema, indent=2)}"
        elif response_format and response_format.get("type") == "json_object":
            prompt = f"{prompt}\n\nPlease respond with a valid JSON object."

        # Apply chat template
        formatted_prompt = apply_chat_template(
            self.processor,
            self.config,
            prompt,
            num_images=num_images
        )

        # Generate response
        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        result = await asyncio.to_thread(
            generate,
            self.model,
            self.processor,
            formatted_prompt,
            images,
            max_tokens=max_tok,
            temp=temp,
            verbose=self.verbose
        )

        # Extract text from result
        if hasattr(result, 'text'):
            response_text = result.text
        else:
            response_text = str(result)

        # Explicit memory cleanup after generation
        mx.clear_cache()
        gc.collect()

        # Always clean JSON responses from MLX models (they often have formatting issues)
        # This is especially important for smaller models like 2B
        response_text = self._clean_json_response(response_text)

        return MLXChatCompletion(response_text)

    def _clean_json_response(self, text: str) -> str:
        """Remove markdown code fences and fix common JSON issues.

        Args:
            text (str): Raw response text

        Returns:
            str: Cleaned text without markdown formatting
        """
        import re
        import json

        # Remove ```json and ``` markers
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
        elif text.startswith("```"):
            text = text[3:]  # Remove ```

        if text.endswith("```"):
            text = text[:-3]  # Remove trailing ```

        text = text.strip()

        # Try to fix common JSON issues
        # If the model wrapped the JSON in explanation text, try to extract just the JSON
        if not text.startswith('{') and not text.startswith('['):
            # Look for JSON object or array start
            json_start = max(text.find('{'), text.find('['))
            if json_start != -1:
                text = text[json_start:]

        # Remove any trailing text after the JSON
        if text.startswith('{'):
            # Find the matching closing brace
            brace_count = 0
            for i, char in enumerate(text):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        text = text[:i+1]
                        break
        elif text.startswith('['):
            # Find the matching closing bracket
            bracket_count = 0
            for i, char in enumerate(text):
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        text = text[:i+1]
                        break

        text = text.strip()

        # Fix smart quotes and unescaped quotes in JSON strings
        # This is a common issue with LLMs
        try:
            # First try to parse - if it works, we're done
            json.loads(text)
            return text
        except json.JSONDecodeError as e:
            # Try to fix common issues
            # Replace curly quotes with straight quotes
            text = text.replace('\u201c', '"').replace('\u201d', '"')
            text = text.replace('\u2018', "'").replace('\u2019', "'")

            # Fix mismatched quotes (like 'text" or "text')
            # Replace all single quotes with double quotes first
            # This is aggressive but works for most LLM-generated JSON
            lines = []
            for line in text.split('\n'):
                # Skip lines that are just brackets
                if line.strip() in ['{', '}', '[', ']', ',']:
                    lines.append(line)
                    continue

                # For lines with content, normalize quotes
                # If we see a mix of ' and ", convert all to "
                if ':' in line:  # This is a key-value pair
                    # Find the value part (after the :)
                    key_part, _, value_part = line.partition(':')

                    # Keep the key part as-is
                    # Fix the value part - replace all ' with " except escaped ones
                    value_part = value_part.replace("\\'", "<<<ESCAPED_QUOTE>>>")
                    value_part = value_part.replace("'", '"')
                    value_part = value_part.replace("<<<ESCAPED_QUOTE>>>", "\\'")

                    line = key_part + ':' + value_part

                lines.append(line)

            text = '\n'.join(lines)

            # Try to parse again
            try:
                json.loads(text)
                return text
            except json.JSONDecodeError:
                # Last resort: try to fix unescaped inner quotes
                # Find all string values and escape inner quotes
                import re

                def fix_string_value(match):
                    full_match = match.group(0)
                    # Get the content between the outermost quotes
                    content = match.group(1)
                    # Escape any unescaped quotes inside
                    content = content.replace('"', '\\"')
                    return f'"{content}"'

                # Match strings that might have unescaped quotes
                # This regex matches: "..." where ... might contain unescaped "
                text = re.sub(r'"([^"\\]*(?:\\.[^"\\]*)*)"', fix_string_value, text)

                return text

        return text.strip()

    @property
    def chat(self):
        """Property to provide OpenAI-style client.chat.completions.create interface."""
        return MLXChatCompletions(self)


class MLXChatCompletions:
    """Wrapper to provide client.chat.completions.create() interface."""

    def __init__(self, client: MLXClient):
        self.client = client

    @property
    def completions(self):
        """Property to provide client.chat.completions interface."""
        return self

    async def create(self, **kwargs):
        """Create a chat completion."""
        return await self.client.chat_completions_create(**kwargs)


class MLXChatCompletion:
    """OpenAI-compatible chat completion result."""

    def __init__(self, content: str):
        self.choices = [MLXChoice(content)]


class MLXChoice:
    """OpenAI-compatible choice object."""

    def __init__(self, content: str):
        self.message = MLXMessage(content)


class MLXMessage:
    """OpenAI-compatible message object."""

    def __init__(self, content: str):
        self.content = content

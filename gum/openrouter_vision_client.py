#!/usr/bin/env python3
"""
OpenRouter Vision Completion Utility

This utility handles vision completions using OpenRouter with proper error handling
and logging. Uses aiohttp for direct HTTP calls.
"""

import aiohttp
import asyncio
import json
import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
import ssl

# Load environment variables at module level, override existing ones
load_dotenv(override=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenRouterVisionClient:
    """OpenRouter client for vision completions using aiohttp."""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("OPENROUTER_MODEL", "qwen/qwen-2.5-vl-72b-instruct:free")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

        if not self.api_key:
            raise ValueError("OpenRouter API key not found. Check OPENROUTER_API_KEY environment variable.")

        logger.info("OpenRouter Vision Client initialized")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  API Key: {self.api_key[:10] + '...' + self.api_key[-4:] if self.api_key else 'None'}")

    async def vision_completion(
        self,
        text_prompt: str,
        base64_image: str,
        max_tokens: int = 1000,
        temperature: float = 0.1,
        timeout: int = 60
    ) -> str:
        """
        Send a vision completion request to OpenRouter.

        Args:
            text_prompt: Text prompt for the image analysis
            base64_image: Base64 encoded image data
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            timeout: Request timeout in seconds

        Returns:
            The AI response content as a string
        """

        # Prepare the messages with vision content
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": text_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }]

        # Headers with required OpenRouter fields
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",  # Required by OpenRouter
            "X-Title": "GUM AI Vision Analysis"       # Recommended by OpenRouter
        }

        # Request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        logger.info("OpenRouter vision completion request")
        logger.info(f"   Model: {self.model}")
        logger.info(f"   Text prompt length: {len(text_prompt)} characters")
        logger.info(f"   Image size: {len(base64_image)} base64 characters")
        logger.info(f"   Max tokens: {max_tokens}")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:

                    response_text = await response.text()

                    if response.status == 200:
                        result = json.loads(response_text)
                        content = result['choices'][0]['message']['content']

                        if content:
                            logger.info("OpenRouter vision success")
                            logger.info(f"   Response length: {len(content)} characters")
                            return content
                        else:
                            error_msg = "OpenRouter returned empty response"
                            logger.error(f"Error: {error_msg}")
                            raise ValueError(error_msg)
                    else:
                        error_msg = f"OpenRouter API error {response.status}: {response_text}"
                        logger.error(f"Error: {error_msg}")
                        raise RuntimeError(error_msg)

            except asyncio.TimeoutError:
                error_msg = f"OpenRouter request timeout after {timeout}s"
                logger.error(f"Error: {error_msg}")
                raise TimeoutError(error_msg)
            except Exception as e:
                error_msg = f"OpenRouter request failed: {str(e)}"
                logger.error(f"Error: {error_msg}")
                raise


# Global client instance
_openrouter_client = None

async def get_openrouter_vision_client() -> OpenRouterVisionClient:
    """Get the global OpenRouter vision client instance."""
    global _openrouter_client
    if _openrouter_client is None:
        _openrouter_client = OpenRouterVisionClient()
    return _openrouter_client


async def openrouter_vision_completion(
    text_prompt: str,
    base64_image: str,
    max_tokens: int = 1000,
    temperature: float = 0.1
) -> str:
    """
    Convenience function for OpenRouter vision completion.

    Args:
        text_prompt: Text prompt for the image analysis
        base64_image: Base64 encoded image data
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation

    Returns:
        The AI response content as a string
    """
    client = await get_openrouter_vision_client()
    return await client.vision_completion(text_prompt, base64_image, max_tokens, temperature)


async def test_openrouter_vision_client():
    """Test the OpenRouter vision client."""

    print("Testing OpenRouter Vision Client...")

    # Create a simple test image (1x1 red pixel)
    import base64
    from io import BytesIO
    from PIL import Image

    # Create test image
    img = Image.new('RGB', (100, 100), color='red')
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    test_base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

    test_prompt = "What color is this image? Please respond with just the color name."

    try:
        response = await openrouter_vision_completion(
            text_prompt=test_prompt,
            base64_image=test_base64_image,
            max_tokens=10,
            temperature=0.0
        )
        print(f"OpenRouter Vision Success: {response}")
        return True
    except Exception as e:
        print(f"OpenRouter Vision Failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_openrouter_vision_client())
    if success:
        print("OpenRouter vision client is working!")
    else:
        print("OpenRouter vision client has issues.")
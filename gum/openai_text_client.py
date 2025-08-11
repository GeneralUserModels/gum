#!/usr/bin/env python3
"""
OpenAI Text Completion Utility

This utility handles text completions using the official OpenAI Python SDK
with proper error handling and logging.
"""

import asyncio
import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load environment variables at module level, override existing ones
load_dotenv(override=True)

# Set up logging with debug level for httpx
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable httpx debug logging to see exact HTTP requests
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)
httpx_handler = logging.StreamHandler()
httpx_handler.setFormatter(logging.Formatter("HTTPX: %(message)s"))
httpx_logger.addHandler(httpx_handler)


class OpenAITextClient:
    """OpenAI client for text completions using the official OpenAI SDK."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.api_base = os.getenv("OPENAI_API_BASE")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.organization = os.getenv("OPENAI_ORGANIZATION")
        
        logger.info("OpenAI Environment Debug:")
        logger.info(f"   API Key: {self.api_key[:10] + '...' + self.api_key[-4:] if self.api_key else 'None'}")
        logger.info(f"   API Base: {self.api_base or 'Default (https://api.openai.com/v1)'}")
        logger.info(f"   Model: {self.model}")
        logger.info(f"   Organization: {self.organization or 'None'}")
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Check OPENAI_API_KEY environment variable.")
        
        # Initialize the OpenAI client with optional parameters
        client_kwargs = {
            "api_key": self.api_key,
        }
        
        if self.api_base:
            client_kwargs["base_url"] = self.api_base
            
        if self.organization:
            client_kwargs["organization"] = self.organization
        
        self.client = AsyncOpenAI(**client_kwargs)
        
        logger.info("OpenAI Text Client initialized")
        logger.info(f"  API Base: {self.api_base or 'Default'}")
        logger.info(f"  Model: {self.model}")
        logger.info(f"  Organization: {self.organization or 'Default'}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        """
        Send a chat completion request to OpenAI.
        
        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            
        Returns:
            The AI response content as a string
        """
        
        logger.info("OpenAI text completion request")
        logger.info(f"   Model: {self.model}")
        logger.info(f"   Messages: {len(messages)} message(s)")
        logger.info(f"   Max tokens: {max_tokens}")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            content = response.choices[0].message.content
            
            if content:
                logger.info("OpenAI success")
                logger.info(f"   Response length: {len(content)} characters")
                return content
            else:
                error_msg = "OpenAI returned empty response"
                logger.error(f"Error: {error_msg}")
                raise ValueError(error_msg)
                
        except Exception as e:
            error_msg = f"OpenAI request failed: {str(e)}"
            logger.error(f"Error: {error_msg}")
            raise


# Global client instance
_openai_client = None

async def get_openai_text_client() -> OpenAITextClient:
    """Get the global OpenAI text client instance."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAITextClient()
    return _openai_client


async def openai_text_completion(
    messages: List[Dict[str, Any]],
    max_tokens: int = 1000,
    temperature: float = 0.1
) -> str:
    """
    Convenience function for OpenAI text completion.
    
    Args:
        messages: List of message dictionaries
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        
    Returns:
        The AI response content as a string
    """
    client = await get_openai_text_client()
    return await client.chat_completion(messages, max_tokens, temperature)


async def test_openai_text_client():
    """Test the OpenAI text client."""
    
    print("Testing OpenAI Text Client...")
    
    test_messages = [
        {"role": "user", "content": "Hello! Please respond with exactly 'OpenAI text working correctly'."}
    ]
    
    try:
        response = await openai_text_completion(
            messages=test_messages,
            max_tokens=20,
            temperature=0.0
        )
        print(f"OpenAI Text Success: {response}")
        return True
    except Exception as e:
        print(f"OpenAI Text Failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_openai_text_client())
    if success:
        print("OpenAI text client is working!")
    else:
        print("OpenAI text client has issues.")

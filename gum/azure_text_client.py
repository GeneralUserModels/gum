#!/usr/bin/env python3
"""
Azure OpenAI Text Completion Utility

This utility handles text completions using the official Azure OpenAI Python SDK
with proper error handling and logging.
"""

import asyncio
import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI

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


class AzureOpenAITextClient:
    """Azure OpenAI client for text completions using the official Azure OpenAI SDK."""
    
    def __init__(self):
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        
        logger.info("Azure OpenAI Environment Debug:")
        logger.info(f"   API Key: {self.api_key[:10] + '...' + self.api_key[-4:] if self.api_key else 'None'}")
        logger.info(f"   Endpoint: {self.endpoint}")
        logger.info(f"   API Version: {self.api_version}")
        logger.info(f"   Deployment: {self.deployment}")
        
        if not all([self.api_key, self.endpoint, self.api_version]):
            raise ValueError("Azure OpenAI configuration incomplete. Check environment variables.")
        
        # Initialize the Azure OpenAI client
        self.client = AsyncAzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,  # type: ignore
            api_version=self.api_version
        )
        
        logger.info("Azure OpenAI Text Client initialized")
        logger.info(f"  Endpoint: {self.endpoint}")
        logger.info(f"  Deployment: {self.deployment}")
        logger.info(f"  API Version: {self.api_version}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        """
        Send a chat completion request to Azure OpenAI.
        
        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            
        Returns:
            The AI response content as a string
        """
        
        logger.info("Azure OpenAI text completion request")
        logger.info(f"   Deployment: {self.deployment}")
        logger.info(f"   Messages: {len(messages)} message(s)")
        logger.info(f"   Max tokens: {max_tokens}")
        
        try:
            response = await self.client.chat.completions.create(
                model=self.deployment,  # Use deployment name as model
                messages=messages,  # type: ignore
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            content = response.choices[0].message.content
            
            if content:
                logger.info("Azure OpenAI success")
                logger.info(f"   Response length: {len(content)} characters")
                return content
            else:
                error_msg = "Azure OpenAI returned empty response"
                logger.error(f"Error: {error_msg}")
                raise ValueError(error_msg)
                
        except Exception as e:
            error_msg = f"Azure OpenAI request failed: {str(e)}"
            logger.error(f"Error: {error_msg}")
            raise


# Global client instance
_azure_client = None

async def get_azure_text_client() -> AzureOpenAITextClient:
    """Get the global Azure OpenAI text client instance."""
    global _azure_client
    if _azure_client is None:
        _azure_client = AzureOpenAITextClient()
    return _azure_client


async def azure_text_completion(
    messages: List[Dict[str, Any]],
    max_tokens: int = 1000,
    temperature: float = 0.1
) -> str:
    """
    Convenience function for Azure OpenAI text completion.
    
    Args:
        messages: List of message dictionaries
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        
    Returns:
        The AI response content as a string
    """
    client = await get_azure_text_client()
    return await client.chat_completion(messages, max_tokens, temperature)


async def test_azure_text_client():
    """Test the Azure OpenAI text client."""
    
    print("Testing Azure OpenAI Text Client...")
    
    test_messages = [
        {"role": "user", "content": "Hello! Please respond with exactly 'Azure OpenAI text working correctly'."}
    ]
    
    try:
        response = await azure_text_completion(
            messages=test_messages,
            max_tokens=20,
            temperature=0.0
        )
        print(f"Azure OpenAI Text Success: {response}")
        return True
    except Exception as e:
        print(f"Azure OpenAI Text Failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_azure_text_client())
    if success:
        print("Azure OpenAI text client is working!")
    else:
        print("Azure OpenAI text client has issues.")
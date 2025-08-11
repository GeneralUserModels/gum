#!/usr/bin/env python3
"""
Unified AI Client Interface

This utility provides a single interface for both text and vision AI completions,
automatically routing to the appropriate provider (Azure OpenAI for text, OpenRouter for vision).
Returns simple strings for easy integration.
"""

import asyncio
import logging
import random
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Import aiohttp for error handling
try:
    import aiohttp
except ImportError:
    aiohttp = None

# Import our specialized clients
from gum.azure_text_client import azure_text_completion
from gum.openai_text_client import openai_text_completion
from gum.openrouter_vision_client import openrouter_vision_completion
import os

# Load environment variables at module level
load_dotenv(override=True)

# Set up logging
logger = logging.getLogger(__name__)


class UnifiedAIClient:
    """Unified AI client that routes requests to appropriate providers based on modality."""
    
    def __init__(self, 
                 max_retries: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 backoff_factor: float = 2.0,
                 jitter_factor: float = 0.1):
        """
        Initialize the unified AI client with retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds between retries
            backoff_factor: Exponential backoff multiplier
            jitter_factor: Random jitter factor to avoid thundering herd
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter_factor = jitter_factor
        
        # Get text provider from environment (default to azure)
        self.text_provider = os.getenv("TEXT_PROVIDER", "azure").lower()
        
        # Get vision provider from environment (default to openrouter)
        self.vision_provider = os.getenv("VISION_PROVIDER", "openrouter").lower()
        
        logger.info("Unified AI Client initialized")
        
        if self.text_provider == "azure":
            logger.info("   Text: Azure OpenAI")
        elif self.text_provider == "openai":
            logger.info("   Text: OpenAI")
        else:
            logger.warning(f"   Unknown text provider: {self.text_provider}, defaulting to Azure OpenAI")
            self.text_provider = "azure"
            logger.info("   Text: Azure OpenAI")
        
        if self.vision_provider == "openrouter":
            logger.info("   Vision: OpenRouter")
        else:
            logger.warning(f"   Unknown vision provider: {self.vision_provider}, defaulting to OpenRouter")
            self.vision_provider = "openrouter"
            logger.info("   Vision: OpenRouter")
        
        logger.info(f"   Retry config: max_retries={max_retries}, base_delay={base_delay}s, backoff_factor={backoff_factor}")
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        
        # Add random jitter to prevent thundering herd
        if self.jitter_factor > 0:
            jitter = delay * self.jitter_factor * random.random()
            delay += jitter
        
        return delay
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error should be retried.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if the error should be retried
        """
        # Retry on specific error types
        if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return True
        
        if isinstance(error, ValueError):
            # Retry on empty response errors
            error_msg = str(error).lower()
            if "empty response" in error_msg or "no content" in error_msg:
                return True
        
        if isinstance(error, RuntimeError):
            # Retry on server errors (5xx) but not client errors (4xx)
            error_msg = str(error).lower()
            if "500" in error_msg or "502" in error_msg or "503" in error_msg or "504" in error_msg:
                return True
        
        # Retry on connection errors
        if isinstance(error, ConnectionError):
            return True
        
        # Retry on aiohttp client errors if aiohttp is available
        if aiohttp:
            # Check for ClientResponseError specifically
            if hasattr(aiohttp, 'ClientResponseError') and isinstance(error, aiohttp.ClientResponseError):
                status_code = error.status
                # Retry on 5xx server errors, timeouts, and specific connection errors
                # Don't retry on 4xx client errors (400, 401, 403, etc.)
                if status_code >= 500:  # 5xx server errors
                    return True
                elif status_code in [408, 429]:  # Request timeout and rate limit
                    return True
                else:
                    return False  # Don't retry client errors (4xx)
            
            # Generic aiohttp ClientError (connection issues, etc.)
            elif isinstance(error, aiohttp.ClientError):
                return True
        
        # Don't retry on authentication errors, invalid requests, etc.
        return False

    async def text_completion(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        """
        Handle text-only completion using the configured text provider.
        
        Args:
            messages: List of message dictionaries (standard OpenAI format)
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            
        Returns:
            The AI response content as a string
        """
        if self.text_provider == "openai":
            logger.info("Routing to OpenAI for text completion")
            return await openai_text_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
        else:  # Default to Azure OpenAI
            logger.info("Routing to Azure OpenAI for text completion")
            return await azure_text_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
    
    async def vision_completion(
        self,
        text_prompt: str,
        base64_image: str,
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        """
        Handle vision completion using the configured provider with retry logic.
        
        Args:
            text_prompt: Text prompt for the image analysis
            base64_image: Base64 encoded image data
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            
        Returns:
            The AI response content as a string
        """
        logger.info("Routing to OpenRouter for vision completion")
        vision_func = openrouter_vision_completion
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):  # +1 for initial attempt
            try:
                if attempt > 0:
                    delay = self._calculate_delay(attempt - 1)
                    logger.info(f"Retry attempt {attempt}/{self.max_retries} after {delay:.2f}s delay")
                    await asyncio.sleep(delay)
                
                result = await vision_func(
                    text_prompt=text_prompt,
                    base64_image=base64_image,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                # Check if result is empty (treat as failure)
                if not result or result.strip() == "":
                    if attempt == self.max_retries:
                        # Final attempt failed
                        logger.error(f"Vision completion failed after {self.max_retries} retries: Empty response")
                        raise ValueError("Empty response from vision completion after all retries")
                    
                    logger.warning(f"Vision completion returned empty response on attempt {attempt + 1}")
                    continue  # Try again
                
                # Success - return the result
                if attempt > 0:
                    logger.info(f"Vision completion succeeded on retry attempt {attempt}")
                
                return result
                
            except Exception as error:
                last_error = error
                
                if attempt == self.max_retries:
                    # Final attempt failed
                    logger.error(f"Vision completion failed after {self.max_retries} retries: {error}")
                    raise error
                
                if not self._is_retryable_error(error):
                    # Error is not retryable
                    logger.error(f"Vision completion failed with non-retryable error: {error}")
                    raise error
                
                logger.warning(f"Vision completion failed on attempt {attempt + 1}: {error}")
        
        # This should never be reached, but just in case
        if last_error:
            raise last_error
        else:
            raise RuntimeError("Vision completion failed with unknown error")

    async def auto_completion(
        self,
        messages: Optional[List[Dict[str, Any]]] = None,
        text_prompt: Optional[str] = None,
        base64_image: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        """
        Automatically route to text or vision completion based on provided parameters.
        
        Args:
            messages: List of message dictionaries for text completion
            text_prompt: Text prompt for vision completion
            base64_image: Base64 encoded image data for vision completion
            max_tokens: Maximum tokens to generate
            temperature: Temperature for generation
            
        Returns:
            The AI response content as a string
        """
        if base64_image and text_prompt:
            # Vision completion
            logger.info("Auto-routing: Vision completion detected")
            return await self.vision_completion(
                text_prompt=text_prompt,
                base64_image=base64_image,
                max_tokens=max_tokens,
                temperature=temperature
            )
        elif messages:
            # Text completion
            logger.info("Auto-routing: Text completion detected")
            return await self.text_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
        else:
            raise ValueError("Must provide either (text_prompt + base64_image) for vision or (messages) for text")


# Global client instance
_unified_client = None

async def get_unified_client() -> UnifiedAIClient:
    """Get the global unified AI client instance."""
    global _unified_client
    if _unified_client is None:
        _unified_client = UnifiedAIClient()
    return _unified_client


# Convenience functions
async def ai_text_completion(
    messages: List[Dict[str, Any]],
    max_tokens: int = 1000,
    temperature: float = 0.1
) -> str:
    """
    Convenience function for text completion.
    
    Args:
        messages: List of message dictionaries
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        
    Returns:
        The AI response content as a string
    """
    client = await get_unified_client()
    return await client.text_completion(messages, max_tokens, temperature)


async def ai_vision_completion(
    text_prompt: str,
    base64_image: str,
    max_tokens: int = 1000,
    temperature: float = 0.1
) -> str:
    """
    Convenience function for vision completion.
    
    Args:
        text_prompt: Text prompt for the image analysis
        base64_image: Base64 encoded image data
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        
    Returns:
        The AI response content as a string
    """
    client = await get_unified_client()
    return await client.vision_completion(text_prompt, base64_image, max_tokens, temperature)


async def ai_auto_completion(
    messages: Optional[List[Dict[str, Any]]] = None,
    text_prompt: Optional[str] = None,
    base64_image: Optional[str] = None,
    max_tokens: int = 1000,
    temperature: float = 0.1
) -> str:
    """
    Convenience function for auto-routed completion.
    
    Args:
        messages: List of message dictionaries for text completion
        text_prompt: Text prompt for vision completion
        base64_image: Base64 encoded image data for vision completion
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        
    Returns:
        The AI response content as a string
    """
    client = await get_unified_client()
    return await client.auto_completion(messages, text_prompt, base64_image, max_tokens, temperature)


async def test_unified_client():
    """Test the unified AI client with both text and vision."""
    
    print("Testing Unified AI Client...")
    
    # Show current configuration
    text_provider = os.getenv("TEXT_PROVIDER", "azure").lower()
    vision_provider = os.getenv("VISION_PROVIDER", "openrouter").lower()
    print(f"Current text provider: {text_provider}")
    print(f"Current vision provider: {vision_provider}")
    
    # Test text completion
    try:
        print(f"\nTesting text completion with {text_provider}...")
        response = await ai_text_completion(
            messages=[{"role": "user", "content": "Hello! Please respond with 'Text completion working'."}],
            max_tokens=20,
            temperature=0.0
        )
        print(f"Text Success: {response}")
    except Exception as e:
        print(f"Text Failed: {e}")
    
    # Test vision completion
    try:
        print(f"\nTesting vision completion with {vision_provider}...")
        
        # Create a simple test image
        import base64
        from io import BytesIO
        from PIL import Image
        
        img = Image.new('RGB', (50, 50), color='blue')
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        test_base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        response = await ai_vision_completion(
            text_prompt="What color is this image? Just say the color.",
            base64_image=test_base64_image,
            max_tokens=10,
            temperature=0.0
        )
        print(f"Vision Success: {response}")
    except Exception as e:
        print(f"Vision Failed: {e}")
        test_base64_image = None  # Set to None if image creation failed
    
    # Test auto-routing
    try:
        print("\nTesting auto-routing (text)...")
        response = await ai_auto_completion(
            messages=[{"role": "user", "content": "Say 'Auto-routing text works'."}],
            max_tokens=10,
            temperature=0.0
        )
        print(f"Auto-routing Text Success: {response}")
    except Exception as e:
        print(f"Auto-routing Text Failed: {e}")
    
    # Only test vision auto-routing if we have a test image
    if test_base64_image:
        try:
            print(f"\nTesting auto-routing (vision with {vision_provider})...")
            response = await ai_auto_completion(
                text_prompt="What color? Just the color name.",
                base64_image=test_base64_image,
                max_tokens=5,
                temperature=0.0
            )
            print(f"Auto-routing Vision Success: {response}")
        except Exception as e:
            print(f"Auto-routing Vision Failed: {e}")
    else:
        print("\nSkipping auto-routing vision test (no test image)")


if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.INFO)
    
    asyncio.run(test_unified_client())
    print("\nUnified AI Client testing completed!")
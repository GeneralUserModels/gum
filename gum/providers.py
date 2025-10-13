# providers.py

from __future__ import annotations

import asyncio
import base64
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
import json


class ModelProvider(ABC):
    """Abstract base class for model providers.
    
    This class defines the interface that all model providers must implement
    to ensure compatibility with the GUM system.
    """
    
    def __init__(self, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None):
        """Initialize the model provider.
        
        Args:
            model (str): The model name to use.
            api_key (str, optional): API key for authentication.
            api_base (str, optional): Base URL for the API.
        """
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate a chat completion.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys.
            response_format: Optional response format specification.
            temperature: Optional temperature for generation.
            **kwargs: Additional provider-specific parameters.
            
        Returns:
            str: The generated text response.
        """
        pass
    
    @abstractmethod
    async def vision_completion(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate a vision completion (for image analysis).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys.
            response_format: Optional response format specification.
            temperature: Optional temperature for generation.
            **kwargs: Additional provider-specific parameters.
            
        Returns:
            str: The generated text response.
        """
        pass


class OpenAIProvider(ModelProvider):
    """OpenAI model provider implementation."""
    
    def __init__(self, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None):
        super().__init__(model, api_key, api_base)
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                base_url=self.api_base,
                api_key=self.api_key
            )
        return self._client
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate a chat completion using OpenAI API."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            **kwargs
        )
        return response.choices[0].message.content
    
    async def vision_completion(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate a vision completion using OpenAI API."""
        # For OpenAI, vision and chat use the same endpoint
        return await self.chat_completion(messages, response_format, temperature, **kwargs)


class GeminiProvider(ModelProvider):
    """Google Gemini model provider implementation."""
    
    def __init__(self, model: str, api_key: Optional[str] = None, api_base: Optional[str] = None):
        super().__init__(model, api_key, api_base)
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            import google.generativeai as genai
            if not self.api_key or self.api_key == "None":
                raise ValueError("Google API key is required for Gemini models. Set GOOGLE_API_KEY environment variable.")
            genai.configure(api_key=self.api_key)
            self._client = genai
        return self._client
    
    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert OpenAI-style messages to Gemini format."""
        gemini_messages = []
        for message in messages:
            if message["role"] == "user":
                gemini_messages.append({
                    "role": "user",
                    "parts": [{"text": message["content"]}]
                })
            elif message["role"] == "assistant":
                gemini_messages.append({
                    "role": "model",
                    "parts": [{"text": message["content"]}]
                })
        return gemini_messages
    
    def _convert_content_to_gemini_format(self, content: Any) -> List[Dict[str, Any]]:
        """Convert OpenAI-style content to Gemini format."""
        if isinstance(content, str):
            return [{"text": content}]
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append({"text": item["text"]})
                    elif item.get("type") == "image_url":
                        # Extract base64 data from OpenAI format
                        image_url = item["image_url"]["url"]
                        if image_url.startswith("data:image"):
                            # Extract base64 data
                            header, data = image_url.split(",", 1)
                            mime_type = header.split(":")[1].split(";")[0]
                            parts.append({
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": data
                                }
                            })
                else:
                    parts.append({"text": str(item)})
            return parts
        else:
            return [{"text": str(content)}]
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate a chat completion using Gemini API."""
        # Convert messages to Gemini format
        # For Gemini, we need to combine all user messages into a single prompt
        # and handle the conversation history properly
        prompt_parts = []
        
        for message in messages:
            content = message["content"]
            if isinstance(content, list):
                # Handle multimodal content
                parts = self._convert_content_to_gemini_format(content)
                prompt_parts.extend(parts)
            else:
                prompt_parts.append({"text": str(content)})
        
        # If response_format is specified, add JSON formatting instruction
        if response_format and response_format.get("type") == "json_object":
            # Add instruction to format response as JSON
            prompt_parts.append({
                "text": "\n\nPlease respond with valid JSON only, no additional text or formatting."
            })
        
        # Create model instance
        model = self.client.GenerativeModel(self.model)
        
        # Configure generation parameters
        generation_config = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        
        # If JSON format is required, set response_mime_type
        if response_format and response_format.get("type") == "json_object":
            generation_config["response_mime_type"] = "application/json"
        
        # Generate content - Gemini expects a single content parameter
        response = await asyncio.to_thread(
            model.generate_content,
            prompt_parts,
            generation_config=generation_config
        )
        
        return response.text
    
    async def vision_completion(
        self,
        messages: List[Dict[str, Any]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """Generate a vision completion using Gemini API."""
        # For Gemini, vision and chat use the same method
        return await self.chat_completion(messages, response_format, temperature, **kwargs)


def create_provider(
    model: str,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None
) -> ModelProvider:
    """Factory function to create the appropriate model provider.
    
    Args:
        model (str): The model name (e.g., 'gpt-4o-mini', 'gemini-1.5-pro').
        api_key (str, optional): API key for authentication.
        api_base (str, optional): Base URL for the API.
        
    Returns:
        ModelProvider: The appropriate provider instance.
        
    Raises:
        ValueError: If the model provider is not supported.
    """
    model_lower = model.lower()
    
    # OpenAI models
    if any(prefix in model_lower for prefix in ['gpt', 'o1', 'dall-e']):
        return OpenAIProvider(model, api_key, api_base)
    
    # Gemini models
    elif any(prefix in model_lower for prefix in ['gemini', 'claude']):
        return GeminiProvider(model, api_key, api_base)
    
    else:
        # Default to OpenAI for backward compatibility
        return OpenAIProvider(model, api_key, api_base)

# AI Provider Configuration

This document explains how to configure different AI providers for the GUM system.

## Overview

The GUM system uses a unified AI client that supports multiple providers for different tasks:

- **Text Completion**: Azure OpenAI (default) or OpenAI
- **Vision Completion**: OpenRouter (default)

## Provider Configuration

### Text Providers

#### Azure OpenAI (Default)
```bash
# Required environment variables
export AZURE_OPENAI_API_KEY="your-azure-api-key"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_VERSION="2024-02-15-preview"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o"  # Optional, defaults to gpt-4o

# Optional: Explicitly set text provider (defaults to azure)
export TEXT_PROVIDER="azure"
```

#### OpenAI
```bash
# Required environment variables
export OPENAI_API_KEY="your-openai-api-key"

# Optional environment variables
export OPENAI_MODEL="gpt-4o"  # Optional, defaults to gpt-4o
export OPENAI_API_BASE="https://api.openai.com/v1"  # Optional, uses default
export OPENAI_ORGANIZATION="your-org-id"  # Optional

# Set text provider to OpenAI
export TEXT_PROVIDER="openai"
```

### Vision Providers

#### OpenRouter (Default)
```bash
# Required environment variables
export OPENROUTER_API_KEY="your-openrouter-api-key"

# Optional environment variables
export OPENROUTER_MODEL="qwen/qwen-2.5-vl-72b-instruct:free"  # Optional, uses default

# Optional: Explicitly set vision provider (defaults to openrouter)
export VISION_PROVIDER="openrouter"
```

## Usage Examples

### Using Azure OpenAI for Text (Default)
```python
import asyncio
from gum import gum
from gum.observers import Observer

async def main():
    # No special configuration needed - Azure is the default
    async with gum("username", "model") as g:
        # Your GUM code here
        pass

asyncio.run(main())
```

### Using OpenAI for Text
```python
import asyncio
import os
from gum import gum
from gum.observers import Observer

async def main():
    # Set OpenAI as text provider
    os.environ["TEXT_PROVIDER"] = "openai"
    
    async with gum("username", "model") as g:
        # Your GUM code here
        pass

asyncio.run(main())
```

### Testing Different Providers

#### Test OpenAI Client
```bash
python test_openai_client.py
```

#### Test Unified Client with Different Providers
```bash
# Test with Azure OpenAI (default)
python -c "import asyncio; from unified_ai_client import test_unified_client; asyncio.run(test_unified_client())"

# Test with OpenAI
TEXT_PROVIDER=openai python -c "import asyncio; from unified_ai_client import test_unified_client; asyncio.run(test_unified_client())"
```

## Provider Features

| Provider | Text Completion | Vision Completion | Notes |
|----------|----------------|-------------------|-------|
| Azure OpenAI | | | Enterprise-grade, requires Azure subscription |
| OpenAI | | | Direct OpenAI API, requires OpenAI account |
| OpenRouter | | | Multiple vision models, cost-effective |

## Error Handling

The unified client includes automatic retry logic with exponential backoff for transient errors. You can configure retry behavior:

```python
from unified_ai_client import UnifiedAIClient

client = UnifiedAIClient(
    max_retries=5,          # Maximum retry attempts
    base_delay=2.0,         # Base delay in seconds
    max_delay=120.0,        # Maximum delay between retries
    backoff_factor=2.0,     # Exponential backoff multiplier
    jitter_factor=0.1       # Random jitter to prevent thundering herd
)
```

## Environment Variables Reference

### Azure OpenAI
- `AZURE_OPENAI_API_KEY` (required)
- `AZURE_OPENAI_ENDPOINT` (required)
- `AZURE_OPENAI_API_VERSION` (required)
- `AZURE_OPENAI_DEPLOYMENT` (optional, defaults to "gpt-4o")

### OpenAI
- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (optional, defaults to "gpt-4o")
- `OPENAI_API_BASE` (optional, defaults to "https://api.openai.com/v1")
- `OPENAI_ORGANIZATION` (optional)

### OpenRouter
- `OPENROUTER_API_KEY` (required)
- `OPENROUTER_MODEL` (optional, defaults to "qwen/qwen-2.5-vl-72b-instruct:free")

### Provider Selection
- `TEXT_PROVIDER` (optional, "azure" or "openai", defaults to "azure")
- `VISION_PROVIDER` (optional, "openrouter", defaults to "openrouter")

## Troubleshooting

### Common Issues

1. **Missing API Keys**: Ensure all required environment variables are set
2. **Network Issues**: Check firewall/proxy settings
3. **Rate Limits**: The client includes automatic retry with backoff
4. **Model Availability**: Verify the model name is correct for your provider

### Debug Logging

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will show detailed HTTP requests and responses for debugging.

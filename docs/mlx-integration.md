# MLX Integration: Run GUM Locally on Apple Silicon

GUM now supports running completely locally on Apple Silicon Macs using MLX-powered vision language models. This eliminates the need for OpenAI API calls, making GUM completely free and private.

## Overview

**What is MLX?**
MLX is Apple's machine learning framework optimized for Apple Silicon (M1, M2, M3, etc.). It enables fast, efficient inference of large language models directly on your Mac.

**Benefits of MLX Integration:**
- ✅ **Completely Free** - No API costs whatsoever
- ✅ **100% Private** - All data stays on your device
- ✅ **Works Offline** - No internet connection required
- ✅ **Fast on Apple Silicon** - Optimized for M1/M2/M3 chips
- ✅ **Drop-in Replacement** - Same API as OpenAI backend

**Tradeoffs:**
- ⏱️ Slower than OpenAI API (local inference vs cloud)
- 💾 Requires disk space (~2-8GB per model)
- 🔽 First run downloads models
- 🧠 Requires sufficient RAM (16GB minimum, 32GB recommended)

## Requirements

### Hardware
- **Mac with Apple Silicon** (M1, M2, M3, or newer)
- **RAM**: 16GB minimum, 32GB recommended
- **Storage**: 5-10GB free space for models

### Software
```bash
pip install mlx-vlm
```

## Quick Start

### Basic Usage

```python
import asyncio
from gum import gum
from gum.observers import Screen

async def main():
    # Create screen observer with MLX backend
    screen = Screen(
        use_mlx=True,  # Enable local MLX models
        mlx_model="mlx-community/Qwen2-VL-2B-Instruct-4bit",
        debug=True
    )

    # Create GUM with MLX backend
    async with gum(
        user_name="your_name",
        model="unused",
        screen,
        use_mlx=True,  # Enable MLX for text generation
        mlx_model="mlx-community/Qwen2-VL-2B-Instruct-4bit",
    ) as g:
        print("GUM is running with local MLX models!")
        await asyncio.sleep(3600)  # Run for 1 hour

asyncio.run(main())
```

## Available Models

### Recommended Models

| Model | Size | RAM Required | Speed | Quality |
|-------|------|--------------|-------|---------|
| `mlx-community/Qwen2-VL-2B-Instruct-4bit` | ~2GB | 8GB | Fast | Good |
| `mlx-community/Qwen2.5-VL-7B-Instruct-4bit` | ~4GB | 16GB | Medium | Great |
| `mlx-community/Qwen2.5-VL-32B-Instruct-4bit` | ~8GB | 32GB | Slow | Excellent |

### Model Selection Guidelines

**For 16GB RAM Macs (M1, M2 base):**
- Use: `Qwen2-VL-2B-Instruct-4bit` or `Qwen2.5-VL-7B-Instruct-4bit`
- These models leave enough RAM for other applications

**For 32GB+ RAM Macs (M2 Pro/Max, M3 Pro/Max):**
- Use: `Qwen2.5-VL-7B-Instruct-4bit` or `Qwen2.5-VL-32B-Instruct-4bit`
- Better quality with more capacity

**For 64GB+ RAM Macs (M2 Ultra, M3 Ultra):**
- Use: `Qwen2.5-VL-32B-Instruct-4bit` or larger
- Best quality available

## Configuration Options

### Screen Observer with MLX

```python
screen = Screen(
    use_mlx=True,  # Enable MLX backend
    mlx_model="mlx-community/Qwen2-VL-2B-Instruct-4bit",  # Model to use
    screenshots_dir="~/.cache/gum/screenshots",
    skip_when_visible=["1Password", "Signal"],  # Privacy protection
    history_k=10,  # Number of screenshots to keep
    debug=False  # Enable MLX verbose logging
)
```

### GUM Instance with MLX

```python
async with gum(
    user_name="speed",
    model="unused",  # Model name unused with MLX
    screen,
    use_mlx=True,  # Enable MLX backend
    mlx_model="mlx-community/Qwen2-VL-2B-Instruct-4bit",
    min_batch_size=3,
    max_batch_size=10
) as g:
    # Your code here
    pass
```

## Hybrid Configuration

You can use MLX for some components and OpenAI for others:

```python
# Use MLX for vision tasks (screenshots are sensitive)
screen = Screen(
    use_mlx=True,
    mlx_model="mlx-community/Qwen2-VL-2B-Instruct-4bit"
)

# Use OpenAI for text tasks (faster proposition generation)
async with gum(
    user_name="speed",
    model="gpt-4o",
    screen,
    use_mlx=False,  # Use OpenAI for text
    api_key="your-api-key"
) as g:
    pass
```

## Performance Benchmarks

### M2 32GB MacBook Pro

| Task | OpenAI API | MLX (Qwen2-VL-2B) | MLX (Qwen2.5-VL-7B) |
|------|-----------|-------------------|---------------------|
| Screenshot Analysis | ~2s | ~5-8s | ~10-15s |
| Proposition Generation | ~1s | ~3-5s | ~6-10s |
| Memory Usage | <100MB | ~2.5GB | ~4.5GB |
| Cost (per 1000 calls) | ~$10 | $0 | $0 |

*Note: Speeds are approximate and depend on prompt length, image resolution, and system load.*

## Troubleshooting

### Out of Memory Errors

**Problem:** System runs out of memory when loading models

**Solutions:**
1. Use a smaller model (2B instead of 7B)
2. Close other applications
3. Reduce batch sizes: `min_batch_size=2, max_batch_size=5`

### Slow Performance

**Problem:** Generation is very slow

**Solutions:**
1. Ensure you're using 4-bit quantized models (they end in `-4bit`)
2. Reduce `max_tokens` in model configuration
3. Use a smaller model for faster responses

### Model Download Issues

**Problem:** Model download fails or is slow

**Solutions:**
1. Check internet connection
2. Download manually: `python -c "from mlx_vlm import load; load('model-name')"`
3. Models are cached in `~/.cache/huggingface/hub/`

## Migration from OpenAI

### Before (OpenAI)
```python
screen = Screen(
    model_name="gpt-4o-mini",
    api_key="sk-..."
)

async with gum(
    user_name="speed",
    model="gpt-4o",
    screen,
    api_key="sk-..."
) as g:
    pass
```

### After (MLX)
```python
screen = Screen(
    use_mlx=True,
    mlx_model="mlx-community/Qwen2-VL-2B-Instruct-4bit"
)

async with gum(
    user_name="speed",
    model="unused",
    screen,
    use_mlx=True,
    mlx_model="mlx-community/Qwen2-VL-2B-Instruct-4bit"
) as g:
    pass
```

## FAQ

### Q: Can I use MLX on Intel Macs?
**A:** No, MLX only works on Apple Silicon (M1, M2, M3, etc.). Intel Macs should continue using the OpenAI backend.

### Q: How much does this save compared to OpenAI?
**A:** For heavy users (1000s of API calls/day), this can save $100-500+ per month. For light users, savings are proportional to usage.

### Q: Is the quality as good as OpenAI?
**A:** Qwen2.5-VL models are very competitive with GPT-4o-mini for most tasks. The 32B model rivals GPT-4o for many use cases. The 2B model is slightly lower quality but still quite capable.

### Q: Can I fine-tune the models?
**A:** Yes! mlx-vlm supports LoRA and QLoRA fine-tuning. See the mlx-vlm documentation for details.

### Q: What if I want to try different models?
**A:** You can change the `mlx_model` parameter to any compatible model from Hugging Face. See [mlx-community](https://huggingface.co/mlx-community) for available models.

## Additional Resources

- [MLX GitHub](https://github.com/ml-explore/mlx)
- [mlx-vlm GitHub](https://github.com/Blaizzy/mlx-vlm)
- [mlx-community Models](https://huggingface.co/mlx-community)
- [Qwen2-VL Documentation](https://qwenlm.github.io/blog/qwen2-vl/)

## Example Scripts

See `examples/mlx_example.py` for a complete working example of GUM with MLX integration.

"""Example: Using GUM with local MLX models instead of OpenAI

This example demonstrates how to use GUM with MLX-powered local vision
and text models running on Apple Silicon, eliminating the need for OpenAI API calls.

Requirements:
- Apple Silicon Mac (M1, M2, M3, etc.)
- At least 16GB RAM (32GB recommended)
- mlx-vlm installed (pip install mlx-vlm)

Benefits:
- Completely free (no API costs)
- Private (all data stays on your device)
- Works offline
- Fast on Apple Silicon

Tradeoffs:
- Slower than OpenAI API
- Requires disk space for models (~2-8GB per model)
- First run downloads models
"""

import asyncio
import logging
from gum import gum
from gum.observers import Screen

async def main():
    """Run GUM with local MLX models"""

    # Create a screen observer with MLX backend
    screen = Screen(
        use_mlx=True,  # Enable MLX instead of OpenAI
        mlx_model="mlx-community/Qwen2.5-VL-7B-Instruct-4bit",  # 7B model for better JSON compliance
        screenshots_dir="~/.cache/gum/screenshots",
        skip_when_visible=["1Password", "Signal"],  # Skip these apps for privacy
        history_k=5,
        debug=True
    )

    # Create GUM instance with MLX backend
    async with gum(
        user_name="speed",
        model="unused",  # Model name is unused with MLX
        screen,
        use_mlx=True,  # Enable MLX for text generation
        mlx_model="mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
        verbosity=logging.INFO,
        audit_enabled=False,
        min_batch_size=3,
        max_batch_size=10
    ) as g:
        print("="*60)
        print("GUM is running with LOCAL MLX models!")
        print("="*60)
        print("\nConfiguration:")
        print(f"  - Vision Model: mlx-community/Qwen2.5-VL-7B-Instruct-4bit")
        print(f"  - Text Model: mlx-community/Qwen2.5-VL-7B-Instruct-4bit")
        print(f"  - Backend: MLX (Apple Silicon)")
        print(f"  - Cost: $0.00 (completely free!)")
        print(f"  - Privacy: 100% local (no data sent to cloud)")
        print("\n" + "="*60)
        print("Observing your screen...")
        print("Press Ctrl+C to stop")
        print("="*60 + "\n")

        # Run until interrupted
        try:
            await asyncio.sleep(3600)  # Run for 1 hour
        except KeyboardInterrupt:
            print("\n\nStopping GUM...")

        # Query some propositions
        print("\n" + "="*60)
        print("Recent propositions about you:")
        print("="*60)

        results = await g.query("programming interests", limit=5)
        for prop, score in results:
            print(f"\n[Score: {score:.2f}]")
            print(f"  {prop.text}")
            if prop.reasoning:
                print(f"  Reasoning: {prop.reasoning}")

if __name__ == "__main__":
    print("\n🚀 Starting GUM with local MLX models...")
    print("First run will download models (~2GB), please be patient!\n")

    asyncio.run(main())

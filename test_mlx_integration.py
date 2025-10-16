"""Quick test of MLX integration with GUM"""
import asyncio
import logging
from gum import gum
from gum.schemas import Update

async def test_mlx_integration():
    """Test MLX backend with GUM's proposition system"""

    print("="*60)
    print("Testing MLX Integration with GUM")
    print("="*60)

    # Create GUM instance with MLX backend using 7B model (better JSON compliance)
    async with gum(
        user_name="speed",
        model="unused",
        use_mlx=True,
        mlx_model="mlx-community/Qwen2.5-VL-7B-Instruct-4bit",
        verbosity=logging.INFO,
        min_batch_size=1,
        max_batch_size=1
    ) as g:
        print("\n✅ GUM initialized with MLX backend")
        print(f"   Model: mlx-community/Qwen2.5-VL-7B-Instruct-4bit (7B)")
        print(f"   RAM Usage: ~4.5GB")
        print(f"   Cost: $0.00 (running locally!)")

        # Create a test observation
        print("\n" + "="*60)
        print("Simulating an observation...")
        print("="*60)

        observation_text = """
User is reading documentation about MLX-VLM on GitHub.
The documentation shows installation steps and example code for vision-language models.
User appears to be researching local AI model alternatives to OpenAI.
        """.strip()

        print(f"\nObservation:\n{observation_text}")

        # Manually create a simple test by calling the proposition constructor
        print("\n" + "="*60)
        print("Generating propositions using local MLX model...")
        print("="*60)

        update = Update(content=observation_text, content_type="input_text")

        try:
            # Generate propositions using MLX
            # First, let's see what the raw MLX response looks like
            prompt = (
                g.propose_prompt.replace("{user_name}", g.user_name)
                .replace("{inputs}", update.content)
            )

            from gum.schemas import get_schema, PropositionSchema
            schema = PropositionSchema.model_json_schema()

            print("\nCalling MLX model...")
            rsp = await g.client.chat.completions.create(
                model=g.model,
                messages=[{"role": "user", "content": prompt}],
                response_format=get_schema(schema),
            )

            raw_response = rsp.choices[0].message.content
            print(f"\nRaw MLX Response:\n{raw_response}\n")
            print("="*60)

            import json

            # Try to parse the response
            try:
                parsed = json.loads(raw_response)
            except json.JSONDecodeError as e:
                print(f"JSON parse error: {e}")
                print("Attempting to fix JSON...")

                # More aggressive JSON fixing
                import re
                fixed = raw_response

                # Fix 1: Replace '.', with ",
                fixed = fixed.replace(".',", '",')
                # Fix 2: Replace .'  with "
                fixed = fixed.replace(".'", '"')

                # Fix 3: Replace 'text" with "text" (mismatched quotes)
                fixed = re.sub(r"'([^']*?)\"", r'"\1"', fixed)
                # Fix 4: Replace "text' with "text"
                fixed = re.sub(r"\"([^\"]*?)'", r'"\1"', fixed)

                # Fix 5: Remove any remaining single quotes that are boundaries
                # Find all string values and normalize their quotes
                lines = fixed.split('\n')
                new_lines = []
                for line in lines:
                    if ':' in line and not line.strip().startswith('//'):
                        # This is a key-value pair
                        # Replace all remaining single quotes with double in the value part
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            key, value = parts
                            # In the value, replace single quotes with double
                            value = value.replace("'", '"')
                            line = key + ':' + value
                    new_lines.append(line)
                fixed = '\n'.join(new_lines)

                print(f"Fixed JSON (first 500 chars):\n{fixed[:500]}\n")

                # Try parsing again
                try:
                    parsed = json.loads(fixed)
                except json.JSONDecodeError as e2:
                    print(f"Still couldn't parse after fixes: {e2}")
                    print("\n✅ MLX model generated a response (but JSON parsing failed)")
                    print("This is a known issue with smaller models - consider using a larger model")
                    print("or implementing more robust JSON fixing.")
                    return False

            # Check if it's an array or object
            if isinstance(parsed, list):
                print(f"\n⚠️  Response is an array, wrapping in propositions object")
                propositions = parsed
            elif isinstance(parsed, dict) and 'propositions' in parsed:
                propositions = parsed["propositions"]
            else:
                print(f"\n⚠️  Unexpected response format: {type(parsed)}")
                return False

            print(f"\n✅ Generated {len(propositions)} propositions locally!")
            print("\nPropositions:")
            for i, prop in enumerate(propositions, 1):
                print(f"\n{i}. {prop['proposition']}")
                print(f"   Reasoning: {prop['reasoning']}")
                if 'confidence' in prop:
                    print(f"   Confidence: {prop['confidence']}")
                if 'decay' in prop:
                    print(f"   Decay: {prop['decay']}")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

        print("\n" + "="*60)
        print("✅ MLX Integration Test PASSED!")
        print("="*60)
        print("\nMLX is working! You can now:")
        print("  - Run GUM with zero API costs")
        print("  - Keep all data 100% private on your device")
        print("  - Work offline without internet")
        print("  - Use examples/mlx_example.py for full screen capture")
        print("="*60)

        return True

if __name__ == "__main__":
    print("\n🚀 Testing MLX Integration...")
    print("(First run downloads model - may take a minute)\n")

    success = asyncio.run(test_mlx_integration())

    if success:
        print("\n🎉 Ready to use GUM with MLX!")
    else:
        print("\n⚠️  Test failed - check errors above")

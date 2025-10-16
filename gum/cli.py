from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))

import os
import argparse
import asyncio
import shutil  
from gum import gum
from gum.observers import Screen

class QueryAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            setattr(namespace, self.dest, '')
        else:
            setattr(namespace, self.dest, values)

def parse_args():
    parser = argparse.ArgumentParser(description='GUM - A Python package with command-line interface')
    parser.add_argument('--user-name', '-u', type=str, help='The user name to use')
    
    parser.add_argument(
        '--query', '-q',
        nargs='?',
        action=QueryAction,
        help='Query the GUM with an optional query string',
    )
    
    parser.add_argument('--limit', '-l', type=int, help='Limit the number of results', default=10)
    parser.add_argument('--model', '-m', type=str, help='Model to use')
    parser.add_argument('--reset-cache', action='store_true', help='Reset the GUM cache and exit')  # Add this line

    # MLX configuration arguments
    parser.add_argument('--use-mlx', action='store_true', help='Use local MLX models instead of OpenAI (Apple Silicon only)')
    parser.add_argument('--mlx-model', type=str, help='MLX model to use (default: mlx-community/Qwen2.5-VL-7B-Instruct-4bit)')

    # Batching configuration arguments
    parser.add_argument('--min-batch-size', type=int, help='Minimum number of observations to trigger batch processing')
    parser.add_argument('--max-batch-size', type=int, help='Maximum number of observations per batch')

    args = parser.parse_args()

    if not hasattr(args, 'query'):
        args.query = None

    return args

async def main():
    args = parse_args()

    # Handle --reset-cache before anything else
    if getattr(args, 'reset_cache', False):
        cache_dir = os.path.expanduser('~/.cache/gum/')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            print(f"Deleted cache directory: {cache_dir}")
        else:
            print(f"Cache directory does not exist: {cache_dir}")
        return

    model = args.model or os.getenv('MODEL_NAME') or 'gpt-4o-mini'
    user_name = args.user_name or os.getenv('USER_NAME')

    # MLX configuration - follow same pattern as other args
    use_mlx = args.use_mlx or os.getenv('USE_MLX', '').lower() in ('true', '1', 'yes')
    mlx_model = args.mlx_model or os.getenv('MLX_MODEL') or 'mlx-community/Qwen2.5-VL-7B-Instruct-4bit'

    # Batching configuration - follow same pattern as other args
    min_batch_size = args.min_batch_size or int(os.getenv('MIN_BATCH_SIZE', '5'))
    max_batch_size = args.max_batch_size or int(os.getenv('MAX_BATCH_SIZE', '15'))

    # you need one or the other
    if user_name is None and args.query is None:
        print("Please provide a user name (as an argument, -u, or as an env variable) or a query (as an argument, -q)")
        return
    
    if args.query is not None:
        gum_instance = gum(user_name, model, use_mlx=use_mlx, mlx_model=mlx_model)
        await gum_instance.connect_db()
        result = await gum_instance.query(args.query, limit=args.limit)
        
        # confidences / propositions / number of items returned
        print(f"\nFound {len(result)} results:")
        for prop, score in result:
            print(f"\nProposition: {prop.text}")
            if prop.reasoning:
                print(f"Reasoning: {prop.reasoning}")
            if prop.confidence is not None:
                print(f"Confidence: {prop.confidence:.2f}")
            print(f"Relevance Score: {score:.2f}")
            print("-" * 80)
    else:
        backend = "MLX (local)" if use_mlx else f"OpenAI ({model})"
        print(f"Listening to {user_name} with {backend}")
        if use_mlx:
            print(f"Using local model: {mlx_model}")
            print("Cost: $0.00 (completely free!)")

        async with gum(
            user_name,
            model,
            Screen(model, use_mlx=use_mlx, mlx_model=mlx_model),
            use_mlx=use_mlx,
            mlx_model=mlx_model,
            min_batch_size=min_batch_size,
            max_batch_size=max_batch_size
        ) as gum_instance:
            await asyncio.Future()  # run forever (Ctrl-C to stop)

def cli():
    asyncio.run(main())

if __name__ == '__main__':
    cli()
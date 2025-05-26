from dotenv import load_dotenv
load_dotenv()

import argparse
import asyncio
from gum import gum
from gum.observers import Screen

def parse_args():
    parser = argparse.ArgumentParser(description='GUM - A Python package with command-line interface')
    parser.add_argument('--user-name', '-u', type=str, required=True, help='The user name to use')
    return parser.parse_args()

async def main():
    args = parse_args()
    print(f"User Name: {args.user_name}")
    async with gum(args.user_name, Screen()):
        await asyncio.Future()  # run forever (Ctrl-C to stop)

if __name__ == '__main__':
    asyncio.run(main())
# GUM (General User Models)

[![arXiv](https://img.shields.io/badge/arXiv-2505.10831-b31b1b.svg)](https://arxiv.org/abs/2505.10831)

## Documentation

We have some early auto-generated docs here: [docs/gum.md](docs/gum.md)

This is very much an alpha release---things will get a lot cleaner and less buggy very soon. In the mean time, feel free to follow the instructions below.

## Installation

> [!WARNING]
> This repository uses GPT 4.1 as a placeholder. However, we **STRONGLY** encourage users to deploy their own local models to serve GUMs. Our paper uses Qwen 2.5 VL and Llama 3.3. We use the OpenAI ChatCompletions API, but awesome open source inference projects like vLLM support the endpoint.

The easiest way to set up is to download the package from pip:

```bash
pip install gum-ai
```

Alternatively, you can install from source. As of now, we've only tested MacOS:
```bash
git clone https://github.com/GeneralUserModels/gum
cd gum
pip install -e .
```

## Usage

0. Make sure you've set up your ENV variables. Create a .env file with an OPENAI_API_KEY.

1. Basic setup:

```python
# Make sure to set OPENAI API ENV variables

import asyncio
from gum import gum
from gum.observers import Screen

async def main():
    async with gum("Omar Shaikh", Screen()):
        await asyncio.Future() # run forever (Ctrl-C to stop)

if __name__ == "__main__":
    asyncio.run(main())
```

2. Use the example to start a server:

```bash
python examples/start_gum.py -u "Your Name"
```

3. Setting up an MCP:

Check out [this repository](https://github.com/GeneralUserModels/gum-mcp) for using GUMs with MCP.

## Project Structure

- `gum/`: Main package directory
  - `gum.py`: Core functionality and gum classes
  - `models.py`: Database models and schemas
  - `db_utils.py`: Database utilities
  - `observers/`: Observer implementations
  - `cli.py`: Command-line interface
  - `prompts/`: Prompt templates

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Citation and Paper

If you're interested in reading more, please check out our paper!

[Creating General User Models from Computer Use](https://arxiv.org/abs/2505.10831)

```bibtex
@misc{shaikh2025creatinggeneralusermodels,
    title={Creating General User Models from Computer Use}, 
    author={Omar Shaikh and Shardul Sapkota and Shan Rizvi and Eric Horvitz and Joon Sung Park and Diyi Yang and Michael S. Bernstein},
    year={2025},
    eprint={2505.10831},
    archivePrefix={arXiv},
    primaryClass={cs.HC},
    url={https://arxiv.org/abs/2505.10831}, 
}
```

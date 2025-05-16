# GUM (General User Models)

[![arXiv](https://img.shields.io/badge/arXiv-2403.xxxxx-b31b1b.svg)](https://arxiv.org/abs/2403.xxxxx)

## Documentation

Coming soon! This is very much an alpha release---things will get a lot cleaner and less buggy very soon. In the mean time, feel free to follow the instructions below.

## Installation

> [!WARNING]
> This repository uses GPT 4.1 as a placeholder. However, we **STRONGLY** encourage users to deploy their own local models to serve GUMs. Our paper uses Qwen 2.5 VL and Llama 3.3. We use the OpenAI ChatCompletions API, but awesome open source inference projects like vLLM support the endpoint.

Install from source for now (package coming soon!):

```bash
git clone https://github.com/GeneralUserModels/gum
cd gum
pip install -e .
```

## Usage

1. Basic setup:

```python
from gum import gum
from gum.observers import YourObserver  # Replace with actual observer

async with gum("user_name") as g:
    # Add observers
    observer = YourObserver()
    g.add_observer(observer)
    
    # The system will automatically start processing updates
    # Wait or perform other operations
```

2. Using the CLI:

```bash
gum start --user-name "your_name"
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

## Citation and Paper!

If you're interested in reading more, please check out our paper!

[Creating General User Models from Computer Use](https://arxiv.org/abs/2403.xxxxx)

```bibtex
@article{shaikh2025gums,
    title={Creating General User Models from Computer Use},
    author={Shaikh, Omar and Sapkota, Shardul and Rizvi, Shan and Horvitz, Eric and Park, Joon Sung and Yang, Diyi and Bernstein, Michael S.},
    journal={arXiv preprint},
    year={2025}
}
```

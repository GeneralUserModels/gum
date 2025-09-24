# GUM (General User Models)

[![arXiv](https://img.shields.io/badge/arXiv-2505.10831-b31b1b.svg)](https://arxiv.org/abs/2505.10831)

General User Models learn about you by observing any interaction you have with your computer. The GUM takes as input any unstructured observation of a user (e.g., device screenshots) and constructs confidence-weighted propositions that capture the user's knowledge and preferences. GUMs introduce an architecture that infers new propositions about a user from multimodal observations, retrieves related propositions for context, and continuously revises existing propositions.

## Documentation

**Full setup and usage docs live here: [https://generalusermodels.github.io/gum/](https://generalusermodels.github.io/gum/)**

## Record and Induce Human Workflows

This repository also contains a macOS recorder (`record/`) and induction utilities (`induce/`) for capturing and processing human-computer interaction traces.

### Record Human Computer-Use Activities

Install the recording tool:

```bash
cd record
pip install -e .
```

Follow the [instructions](record/instructions.pdf) to configure the required system settings.

Run the recorder CLI directly from the repo (no install required):

```bash
python -m record.gum
```

If you've installed the package with `pip install -e .`, you can instead invoke the console script:

```bash
gum
```

Both commands launch the macOS recorder and begin logging activities.

### Induce Human Workflows

Install dependencies and run the induction pipeline against a directory that contains recorded sessions (defaults to `~/Downloads/records`):

```bash
cd ../induce
pip install -r requirements.txt
python get_human_trajectory.py --data_dir <data_dir>
python segment.py --data_dir <data_dir>
python induce.py --data_dir <data_dir> --auto
```

`get_human_trajectory.py` merges duplicate actions, `segment.py` detects state transitions, and `induce.py` performs semantic-based segment merging. The resulting workflow artifacts are saved to `{data_dir}/workflow.json` and `{data_dir}/workflow.txt`.

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

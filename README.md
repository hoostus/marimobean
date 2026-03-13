# Quickstart

1. Install uv, if not already installed.
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Run a Marimo notebook using uv.
```
uv run marimo run pnl.py
```

# Getting Started

These are a collection of [Marimo](https://marimo.io/) notebooks that showcase exploring
[beancount](https://beancount.github.io/docs/) plaintext accounting data in various ways.

All of them should be runnable from this directory
directly with [uv] (https://docs.astral.sh/uv/) which will
handle installing the dependencies in a virtual environment for you.

```uv run marimo edit <filename.py>```

The top of each file will have a variable ```beancount_file``` which you
will need to edit to point to your actual beancount file.

## marimo edit vs marimo run

*marimo edit* allows you to edit the notebook, *marimo run* doesn't. This
read-only version of the notebook is suitable for serving as a simple app
to non-technical users.

# Example Beancount Files

There are example beancount files provided from the [fava](https://github.com/beancount/fava)
project to let you get started right away with examples and demos.
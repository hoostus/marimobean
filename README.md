![screen shot of PNL notebook](https://github.com/hoostus/marimobean/blob/main/screenshot-1.png?raw=true)
![screen shot of Annual Expense Comparison notebook](https://github.com/hoostus/marimobean/blob/main/screenshot-2.png?raw=true)

# Quickstart

## Experimenting without local installation

Click [this link](https://molab.marimo.io/github.com/hoostus/marimobean/blob/main/pnl.py).

**Result:** the notebook will be open in the [molab](https://molab.marimo.io/notebooks) site.

Click the **Run in molab** button  in the top right corner.

Click on the right bottom corner the **Run** button (a triangle, pointing to the right)


## Running notebooks locally

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
directly with [uv](https://docs.astral.sh/uv/) which will
handle installing the dependencies in a virtual environment for you.

```uv run marimo edit <filename.py>```

Somewhere in each file should be a variable ```beancount_file``` (or similar)
which you will need to edit to point to your actual beancount file if you want
to use non-demo data.

## template.py

If you want to create your own, you can copy this file which has a few cells
to help you get up and running quickly.

```cp template.py my_experiment.py```

## marimo edit vs marimo run

*marimo edit* allows you to edit the notebook, *marimo run* doesn't. This
read-only version of the notebook is suitable for serving as a simple app
to non-technical users.

# Example Beancount Files

There are example beancount files provided from the [fava](https://github.com/beancount/fava)
project to let you get started right away with examples and demos.
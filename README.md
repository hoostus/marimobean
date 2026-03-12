These are a collection of [Marimo](https://marimo.io/) notebooks that showcase exploring
[beancount](https://beancount.github.io/docs/) plaintext accounting data in various ways.

All of them should be runnable from this directory
directly with [uv] (https://docs.astral.sh/uv/) which will
handle installing the dependencies in a virtual environment for you.

```uv run marimo edit <filename.py>```

The top of each file will have a variable ```beancount_file``` which you
will need to edit to point to your actual beancount file.
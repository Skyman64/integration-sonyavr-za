# Contributing

Thanks for taking the time to contribute!

Found a bug, typo, missing feature, or a description that doesn't make sense?
Please open an issue.

### Bug reports

Search the [existing issues](https://github.com/Skyman64/integration-sonyavr-za/issues)
first. If it isn't already tracked, [open a new issue](https://github.com/Skyman64/integration-sonyavr-za/issues/new)
with your receiver model, firmware version, and steps to reproduce.

### New features

Describe the problem you want to solve in a
[new issue](https://github.com/Skyman64/integration-sonyavr-za/issues/new)
before submitting a large pull request, so we can agree on the approach first.

### Contributing code

1. Fork the repo and make your changes on a feature branch.
2. Contributed code must be licensed under the
   [Mozilla Public License 2.0](https://choosealicense.com/licenses/mpl-2.0/)
   (or a compatible license, if you're reusing MIT-licensed code from
   elsewhere). Add a copyright header to new files:

    ```python
    """
    {short file description}

    :license: Mozilla Public License Version 2.0, see LICENSE for more details.
    """
    ```

3. Follow the code style below and make sure lint checks pass.
4. Push to your fork and submit a pull request.

## Code style

- Line length: 120 characters.
- Double quotes by default (checked by pylint's quote-consistency check).
- Config: `.pylintrc` (pylint), `setup.cfg` (flake8), `pyproject.toml` `[tool.isort]` (isort).

Install the linting tools:

```bash
pip3 install -r test-requirements.txt
```

Run the same checks used in CI (`.github/workflows/python-code-format.yml`):

```bash
python -m pylint src
python -m flake8 src --count --show-source --statistics
python -m isort src/. --check --verbose
python -m black src --check --diff --verbose --line-length 120
```

Auto-format:

```bash
python -m black src --line-length 120
python -m isort src/.
```

## Protocol reverse-engineering

If you're decoding new frames on your own receiver, use `src/test.py <ip>` to
watch pushed status updates while you change settings on the front panel or
web UI, and update [PROTOCOL.md](PROTOCOL.md) with anything you confirm.
Mark anything you haven't verified live as a *hypothesis* rather than fact.

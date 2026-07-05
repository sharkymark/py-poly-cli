py-poly-cli

Single-file Python CLI (poly_cli.py) using argparse. Multi-function tool; --debug enables extra output. Persists to history.db (SQLite). Deps: requests, halo, python-dateutil, gnews, simple_salesforce.

Environment:
- use the checked-in venv: source venv/bin/activate
- install deps with pip install -r requirements.txt

Run:
- python poly_cli.py --help  (lists subcommands)
- python poly_cli.py --debug ...  for troubleshooting

Test:
- no formal test suite; verify by running the CLI against real subcommands

Conventions:
- keep everything in poly_cli.py unless it clearly warrants splitting
- format and lint with ruff (ruff format, ruff check) if adding code
- do not commit history.db changes or any secrets/tokens

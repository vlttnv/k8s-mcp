lint_format_check:
	ruff check .
	ruff format --check .

lint_format:
	ruff check --fix .
	ruff format .

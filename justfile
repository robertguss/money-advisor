sync:
	uv sync

test:
	uv run pytest

reconcile:
	uv run finances reconcile transactions/

ci:
	cargo fmt --check
	cargo test
	nvim --headless --noplugin -u NONE -l tests/run.lua
	{{env_var_or_default("PYTHON", "python3")}} tests/test_setup.py

setup:
	git config core.hooksPath .githooks

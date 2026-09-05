.PHONY: check-uv lock-check lint typecheck-python quality doctor check test test-fast public-check demo studio visuals-install visuals-check visual-studio vgpu-doctor opencv-install opencv-check pedalboard-install pedalboard-check

UV ?= uv
UV_RUN = $(UV) run --locked
UV_RUN_OPENCV = $(UV) run --locked --extra opencv

check-uv:
	@command -v "$(UV)" >/dev/null 2>&1 || { echo "EPRS development requires uv" >&2; exit 1; }

lock-check: check-uv
	$(UV) lock --check

lint: lock-check
	$(UV_RUN) ruff check src tests scripts

typecheck-python: lock-check
	$(UV_RUN) ty check

quality: lint typecheck-python

doctor: lock-check
	$(UV_RUN) eprs doctor

check: lock-check
	$(UV_RUN) eprs check examples/beats/porchlight-pocket.beat
	$(UV_RUN) eprs check examples/beats/five-window-engine.beat
	$(UV_RUN) eprs check examples/beats/sleep-circuit.beat

test: lock-check
	PYTHONPATH=src $(UV_RUN) python -m unittest discover -s tests -v
	node --test tests-js/*.test.mjs

# Quick control-plane feedback while iterating. Run the full media suite above
# before a checkpoint or handoff.
test-fast: lock-check
	PYTHONPATH=src $(UV_RUN) python -m unittest -v \
		tests.test_adapters tests.test_beat tests.test_context tests.test_daily_context tests.test_evidence \
		tests.test_dispatch \
		tests.test_plan tests.test_plan_progress tests.test_planning \
		 tests.test_request tests.test_research tests.test_frontier tests.test_runner tests.test_runtime tests.test_visuals \
		tests.test_work tests.test_work_origin tests.test_quality
	node --test tests-js/*.test.mjs

public-check: lock-check
	$(UV_RUN) python scripts/check_public_repo.py

demo:
	./scripts/render_demos.sh

studio: lock-check
	$(UV_RUN) python -m http.server 8000 -d studio

visuals-install:
	cd visuals && npm install
	./scripts/eprs render examples/beats/porchlight-pocket.beat --out visuals/public/media/demo.wav

visuals-check:
	cd visuals && npm run typecheck

visual-studio:
	cd visuals && npm run studio

vgpu-doctor:
	cd visuals && npx vgpu doctor

opencv-install: check-uv lock-check
	$(UV) sync --locked --inexact --extra opencv

opencv-check: lock-check
	PYTHONPATH=src $(UV_RUN_OPENCV) python -m unittest -v tests.test_video_quality

pedalboard-install: check-uv lock-check
	$(UV) sync --locked --inexact --extra pedalboard

pedalboard-check: check-uv lock-check
	PYTHONPATH=src $(UV) run --locked --extra pedalboard python -m unittest -v tests.test_pedalboard_fx

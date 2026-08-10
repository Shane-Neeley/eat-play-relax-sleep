.PHONY: doctor check test test-fast public-check demo studio visuals-install visuals-check visual-studio

doctor:
	./scripts/eprs doctor

check:
	./scripts/eprs check examples/beats/porchlight-pocket.beat
	./scripts/eprs check examples/beats/five-window-engine.beat
	./scripts/eprs check examples/beats/sleep-circuit.beat

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
	node --test tests-js/*.test.mjs

# Quick control-plane feedback while iterating. Run the full media suite above
# before a checkpoint or handoff.
test-fast:
	PYTHONPATH=src python3 -m unittest -v \
		tests.test_adapters tests.test_beat tests.test_context tests.test_evidence \
		tests.test_dispatch \
		tests.test_plan tests.test_plan_progress tests.test_planning \
		tests.test_request tests.test_research tests.test_runner tests.test_runtime tests.test_visuals \
		tests.test_work tests.test_work_origin
	node --test tests-js/*.test.mjs

public-check:
	python3 scripts/check_public_repo.py

demo:
	./scripts/render_demos.sh

studio:
	python3 -m http.server 8000 -d studio

visuals-install:
	cd visuals && npm install
	./scripts/eprs render examples/beats/porchlight-pocket.beat --out visuals/public/media/demo.wav

visuals-check:
	cd visuals && npm run typecheck

visual-studio:
	cd visuals && npm run studio

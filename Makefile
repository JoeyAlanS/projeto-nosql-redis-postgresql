.PHONY: up load verify benchmark test browser audit logs stop package all
.NOTPARALLEL: all
up:
	docker compose up -d --build --wait
load:
	docker compose exec -T app python -m scripts.load --records 1000000
verify:
	docker compose exec -T app python -m scripts.verify
benchmark:
	docker compose exec -T app python -m scripts.benchmark --repetitions 30 --warmup 5
test:
	@mkdir -p results
	@docker compose exec -T app python -m unittest discover -s tests -v > results/tests.log 2>&1 || { cat results/tests.log; exit 1; }
	@cat results/tests.log
browser:
	npm run test:browser
audit:
	python3 scripts/audit_delivery.py
logs:
	docker compose logs --tail 50 app
stop:
	docker compose stop
package:
	python3 scripts/package_delivery.py
all: up load verify test benchmark

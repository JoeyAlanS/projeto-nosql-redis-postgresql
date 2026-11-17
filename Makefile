.PHONY: up load verify benchmark test test-console test-tools check browser audit logs stop package all crud exemplos-redis test-exemplos-redis escala graficos
PYTHON_GRAFICOS ?= .venv-graficos/bin/python
.NOTPARALLEL: all check
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
test-console:
	node --test tests/frontend/*.test.mjs
test-tools:
	docker compose exec -T app python -m unittest discover -s tests/scalability -p 'test_*.py' -v
check: test test-console test-exemplos-redis test-tools audit
crud:
	docker compose exec -T app python -m scripts.crud_demo
exemplos-redis:
	docker compose exec -T app python exemplos/redis/01_crud_hash.py
	docker compose exec -T app python exemplos/redis/02_historico_sensor.py
	docker compose exec -T app python exemplos/redis/03_cache_ttl.py
test-exemplos-redis:
	docker compose exec -T app python -m unittest discover -s exemplos/redis -p 'test_*.py' -v
audit:
	python3 scripts/audit_delivery.py
logs:
	docker compose logs --tail 50 app
stop:
	docker compose stop
escala:
	python3 -m scripts.compare_scales
graficos:
	$(PYTHON_GRAFICOS) -m scripts.plot_load_tests
package:
	python3 scripts/package_delivery.py
all: up load verify test benchmark

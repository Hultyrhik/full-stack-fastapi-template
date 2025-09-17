.DEFAULT_GOAL := build_dev


.PHONY: build_dev
build_dev: build_dev_down 
	docker compose watch


.PHONY: build_dev_down
build_dev_down: 
	docker compose down

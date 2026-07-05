.PHONY: help build run stop logs clean install test

DOCKER_IMAGE := sony-avr-za-integration
DOCKER_CONTAINER := sony-avr-za-integration

help:
	@echo "Sony AVR ZA Integration - Docker Commands"
	@echo ""
	@echo "Usage:"
	@echo "  make build       - Build the Docker image"
	@echo "  make run         - Run the integration container"
	@echo "  make stop        - Stop the running container"
	@echo "  make logs        - View container logs"
	@echo "  make shell       - Open a shell in the container"
	@echo "  make clean       - Remove the container and image"
	@echo "  make install     - Install Python dependencies locally"
	@echo "  make test        - Run test suite"
	@echo "  make format      - Format code with black/isort"
	@echo "  make lint        - Run linters (flake8, pylint)"

build:
	docker build -t $(DOCKER_IMAGE) .

run: build
	docker-compose up -d
	@echo "Integration started. Use 'make logs' to view output."

stop:
	docker-compose down

logs:
	docker-compose logs -f $(DOCKER_CONTAINER)

shell:
	docker exec -it $(DOCKER_CONTAINER) /bin/bash

clean:
	docker-compose down
	docker rmi -f $(DOCKER_IMAGE)
	rm -rf __pycache__ .pytest_cache *.pyc

install:
	pip3 install -r requirements.txt

test:
	python3 -m pytest src/ -v

format:
	python3 -m black src/
	python3 -m isort src/

lint:
	python3 -m flake8 src/ --max-line-length=120
	python3 -m pylint src/

# Local development
dev-install:
	pip3 install -r requirements.txt
	pip3 install black isort flake8 pylint pytest

dev-run:
	python3 src/driver.py

dev-test:
	python3 src/test.py 192.168.1.100

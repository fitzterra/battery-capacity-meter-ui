# Make sure we use bash as the shell.
SHELL := /usr/bin/env bash

REGISTRY=darwin:5000
IMAGE_NAME=bat-cap-ui
DOCKERFILE=Dockerfile
COMPOSE_FILE=docker-compose.yml

### These are for the doc generation using pydoctor
# The html output path for the docs
APP_DOC_DIR=doc/app-docs
# A symlink for images we will create inside APP_DOC_DIR that links to the
# `img` dir in the man `doc` dir.
DOC_IMG_LINK=$(APP_DOC_DIR)/img

.PHONY: image dev-setup run stop version bump-major bump-minor bump-patch docs dbshell repl compose-conf show-env

# Get the current version from the VERSION file
VERSION := $(shell cat VERSION)

# Set up a known environment - we have the .env file target that will make the
# .env symlink if needed.
include .env

# Also include any local environment variables if .env_local exists
-include .env_local

# Make sure all the vars we included from the env files are available to any
# recipes we run
export

# Function to increment the major, minor or patch part of the version in the
# VERSION file.
# Call it with: $(call bump_version,1) 
# where the argument after the name is either 1, 2, or 3 depending on if the
# major, minor or patch part respectively needs to be updated.
# The arg we get in will be in $(1) which is expanded to the field number after
# splitting the version string on '.' to get the 3 version parts.
# If 3 is passed as the field arg, all the $$$ then evaluates to:
#   $$3   - after first expansion
# The extra $ is to prevent make from trying to expand that, and will pass that
# part to awk as '$3' which it will take as the field number to increment.
define bump_version
	awk -F. 'BEGIN {OFS="."} {$$$(1)+=1; print $$0}' VERSION > VERSION.tmp && mv VERSION.tmp VERSION
endef


# Build and push Docker image with versioned tags
image:
	@docker build -t $(REGISTRY)/$(IMAGE_NAME):$(VERSION) -t $(REGISTRY)/$(IMAGE_NAME):latest . && \
	docker push $(REGISTRY)/$(IMAGE_NAME) --all-tags && \
	echo "Pushed new version: $(VERSION)"

# Set up the local development environment
dev-setup:
	pip install -r requirements-localdev.txt

# Start the container in the foreground
run:
	docker-compose up

# Stop any running containers
stop:
	docker-compose down

# Print current version
version:
	@cat VERSION

# Manually bump patch part in version
bump-patch:
	@$(call bump_version,3)
	@echo -n "New version: "
	@cat VERSION

# Manually bump minor part in version
bump-minor:
	@$(call bump_version,2)
	@echo -n "New version: "
	@cat VERSION

# Manually bump major part in version
bump-major:
	@$(call bump_version,1)
	@echo -n "New version: "
	@cat VERSION


# Ensure the doc/app-docs/img symlink exists and points to ../img
doc-img-link:
	@mkdir -p $(APP_DOC_DIR)
	@if [ ! -L $(DOC_IMG_LINK) ]; then \
		echo "Creating symlink: $(DOC_IMG_LINK) -> ../img"; \
		ln -s ../img $(DOC_IMG_LINK); \
	elif [ "$$(readlink -f $(DOC_IMG_LINK))" != "$$(readlink -f $(APP_DOC_DIR)/../img)" ]; then \
		echo "Symlink exists but points to the wrong target. Recreating..."; \
		rm -f $(DOC_IMG_LINK); \
		ln -s ../img $(DOC_IMG_LINK); \
	else \
		echo "Correct symlink already exists: $(DOC_IMG_LINK)"; \
	fi

# Make sure we have .env symlinked to dot.env-sample
.env:
	@if [ -L .env ]; then \
		if [ "$$(readlink .env)" = "dot.env-sample" ]; then \
			exit 0; \
		else \
			echo ".env exists but points somewhere else. Recreating symlink."; \
			rm .env; \
		fi; \
	elif [ -e .env ]; then \
		echo ".env exists but is not a symlink. Please fix manually."; \
		exit 1; \
	fi
	@if [ ! -e dot.env-sample ]; then \
		echo "Error: missing dot.env-sample, cannot create .env!"; \
		exit 1; \
	fi
	@echo "Creating symlink: .env -> dot.env-sample"
	ln -s dot.env-sample .env

# Builds the docs using pydoctor. Requires the pydoctor python package to have
# been installed, and also a fully configured pydoctor.ini or similar config
# file for pydoctor
# Also ensure the `img` symlink in the pydoctor output dir to the main doc/img
# dir exists.
docs: doc-img-link
	@# First determine remote gitlab url from the git remote,
	@# and also the current branch. This is used to set the
	@# source URL for the docs
	@remote_url=$$(git config --get remote.origin.url) && \
	branch_name=$$(git branch --show-current) && \
	if [[ $$remote_url == git@* ]]; then \
	  remote_url=$$(echo "$$remote_url" | sed -e 's/:/\//' -e 's/^git@/http:\/\//'); \
	fi && \
	if [[ $$remote_url == *.git ]]; then \
	  remote_url=$${remote_url%.git}; \
	fi && \
	html_url="$$remote_url/blob/$$branch_name/app" && \
	pydoctor --html-output $(APP_DOC_DIR) --project-url "$$remote_url" \
		--html-viewsource-base "$$html_url" --template-dir=./pydoctor_templates

# Connects to the DB using pgcli
# This relies on the DB_??? settings to be in the environment
dbshell:
	@# Source .env and then connect with pgcli
	@pgcli postgres://$${DB_USER}:$${DB_PASS}@$${DB_HOST}/$${DB_NAME}

# Starts a local ipython REPL with the environment set up from .env end
# optionally .env_local as included and then exported above.
# This will allow connecting to the DB and performing DB operations for example
# - if the local dev host can connect to the DB
repl:
	@ipython

## Shows the compose config
compose-conf:
	@docker-compose config

show-env:
	@env

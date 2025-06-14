# Make sure we use bash as the shell.
SHELL := /usr/bin/env bash

# All these variables needs to be set from the .env and or .env_local files
# that are imported below. We just set them as empty values here for
# documentation and for "declaring" everything that is needed.
#
# The docker image registry
REGISTRY=
IMAGE_NAME=
CONTAINER_NAME=
# This is the docker host on which we will deploy the application as a
# container - this should best be set via .env, .env_local or as a variable
# called LOC_DEPLOY_HOST in the repo's CI/CID variables section
DEPLOY_HOST=
# The user on DEPLOY_HOST to deploy as. Deployment will be done by ssh'ing into
# DEPLOY_HOST as this user, so wherever the deployment is done from, the user
# doing the deploymnet on the local machine needs his ssh pub key in the
# authorized_keys of this user on DEPLOY_HOST - this should best be set via
# .env, .env_local or as a variable called LOC_DEPLOY_USER in the repo's CI/CID
# variables section
DEPLOY_USER=
# The name of the image to use when running as docker container
DEPLOY_NAME=
# This is a temp file used for creating the full runtime environment for the
# remote deployment. It will be a combination of .env and .env_local and will
# be SCPd to the deployment host where it will be used as the docker
# environment for the app.
MERGED_ENV=/tmp/$(DEPLOY_NAME).env

### These are for the doc generation using pydoctor
# The html output path for the docs
APP_DOC_DIR=doc/app-docs
# A symlink for images we will create inside APP_DOC_DIR that links to the
# `img` dir in the man `doc` dir.
DOC_IMG_LINK=$(APP_DOC_DIR)/img

.PHONY: help image dev-setup run stop version release docs dbshell repl \
	    rem-repl shell compose-conf show-env docker-prune

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

# A help message ALA heredoc style for makefiles. It depends on the GNU make
# and it multiline variables. See: https://unix.stackexchange.com/a/516476
define help_msg =

The following make targets are available:

dev-setup     - Set up the local development environment by installing requirements etc.
compose-conf  - Shows the full docker compose config
run           - Start the container in the foreground
stop          - Stop any running containers
version       - Show the current app version (from VERSION file)
dbshell       - Connects to the DB using pgcli using DB_??? env vars for config info
repl          - Starts a local ipython REPL with the environment set up from .env .env_local
rem-repl      - Starts REPL in container after installing ipython if not already installed
shell         - Runs bash inside the container
show-env      - Shows the full environment the Makefile sees
docs          - Builds the documentation via pydoctor.
image         - Build and push Docker image with versioned tags
release       - Creates a release. In UAT creates an RC release, and a prod release in main.
docker-prune  - Deletes all stopped containers to reclaim space. Will ask for confirmation.
help          - Show this help message.

endef

# Show the help_msg defined above. To break this down for those not 100%
# familiar with Makefile Syntax:
# * The ; after help: allows you to define the recipe inline on the same line.
# * @ suppresses echoing the command before execution (as usual in Make).
# * $(info ...) is a Make built-in function. It is evaluated by Make itself,
#   not by the shell. It prints the message to stdout at parse time, not run time.
# * The : at the end does nothing in the shell — it is a shell built-in no-op.
#   It's just there to ensure the line has a command that returns true.
help:; @ $(info $(help_msg)) :


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

# Deploy the image for the current version (from the VERSION) file to the
# deploy host.
# The deploy host only has SSH access and can run docker images.
# Since our docker image needs it's full config to be supplied in the
# environment when it is started, we have to supply the docker --env-file arg
# pointing to a full environment file.
# This environment file is make up from .env with .env_local overriding the
# versioned .env default values (.env_local is not versioned)
# We dynamically create the file by cat-ing .env and .env_local into one temp
# file, copy this to the remote as a temp file, use that temp file as the
# docker startup environment, and delete the temp environment once the
# container is up.
deploy:
	@[[ -f .env && -f .env_local ]] || { echo ".env and .env_local is required"; exit 1; }
	@echo "Merging .env and .env_local..."
	@cat .env .env_local 2>/dev/null | grep -E '^[a-zA-Z0-9._]+=' > $(MERGED_ENV)
	@echo "Deploying version $(VERSION) to $(DEPLOY_HOST)..."
	@scp $(MERGED_ENV) $(DEPLOY_USER)@$(DEPLOY_HOST):$(MERGED_ENV)
	@rm -f $(MERGED_ENV)
	@ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "\
		docker pull $(REGISTRY)/$(IMAGE_NAME):$(VERSION) && \
		docker stop $(DEPLOY_NAME) || true && \
		docker rm $(DEPLOY_NAME) || true && \
		docker run -d --name $(DEPLOY_NAME) --env-file $(MERGED_ENV) \
			-p $(DEPLOY_PORT):$(APP_PORT) \
			$(REGISTRY)/$(IMAGE_NAME):$(VERSION) $(IMAGE) && \
		rm -f $(MERGED_ENV) \
		"

# Removes all old stopped containers to reclaim space
docker-prune:
	docker container prune

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

# Creates a release
release:
	@./release_helper.sh

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
	  remote_url=$$(echo "$$remote_url" | sed -e 's/:/\//' -e 's|^git@|http://|'); \
	fi && \
	if [[ $$remote_url == *gitlab-ci-token* ]]; then \
		remote_url=$$(echo "$$remote_url" | sed -e 's|^.*@|https://|'); \
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

# Starts ipython in the container after installing ipython if it is not already
# installed.
rem-repl:
	@docker exec -ti $(CONTAINER_NAME) bash -c "pip install ipython; ipython"


# Runs bash inside the container
shell:
	@docker exec -ti $(CONTAINER_NAME) bash

## Shows the compose config
compose-conf:
	@docker-compose config

## Shows the full environment the Makefile sees
show-env:
	@env

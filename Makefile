# Make sure we use bash as the shell.
SHELL := /usr/bin/env bash

REGISTRY=darwin:5000
IMAGE_NAME=bat-cap-ui
DOCKERFILE=Dockerfile
COMPOSE_FILE=docker-compose.yml
# This should probably be in an env file and imported into the environment
# both for here and also for the compose file.
CONTAINER_NAME=bat-cap-ui
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
DEPLOY_NAME=bat-cap-ui
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

.PHONY: image dev-setup run stop version bump-major bump-minor bump-patch \
	    docs dbshell repl rem-repl shell compose-conf show-env

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
	@ssh -v $(DEPLOY_USER)@$(DEPLOY_HOST) "id && ls -l"
	@exit 1
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

show-env:
	@env

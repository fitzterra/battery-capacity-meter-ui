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
# This is the compose config dir on the remote production host.
# TODO: Currently, the compose config dir on the remote is disconnected from
# the main add due to that compose config dir not being managed and versioned
# by this repo.
# Change this so that we deploy the compose file and environment and manage the
# compose file and environment in this repo.
PROD_COMPOSE_DIR = ~/docker-cfg/bat-cap-ui
PROD_RUNTIME_ENV = $(PROD_COMPOSE_DIR)/.env

### These are for the doc generation using pydoctor
# The html output path for the docs
APP_DOC_DIR=doc/app-docs
# A symlink for images we will create inside APP_DOC_DIR that links to the
# `img` dir in the man `doc` dir.
DOC_IMG_LINK=$(APP_DOC_DIR)/img

# This is the docker image we use for the mermaid cli.
# NOTE: This docker image is HUGE - feel free to delete it if space gets tight:
# docker image rm $MM_CLI_DOCKER
# See: https://github.com/mermaid-js/mermaid-cli?tab=readme-ov-file#alternative-installations
MM_CLI_DOCKER=ghcr.io/mermaid-js/mermaid-cli/mermaid-cli

.PHONY: \
	help \
	dev-setup \
	image \
	deploy \
	test-deploy \
	templates \
	docker-prune \
	run \
	stop \
	version \
	release \
	docs \
	gen-erd \
	dbshell \
	db-clone-uat \
	db-drop-uat-snapshot \
	db-snapshot-uat \
	db-restore-uat \
	db-list \
	repl \
	rem-repl \
	shell \
	compose-conf \
	mr \
	show-env \


# Get the current version from the VERSION file
VERSION := $(shell cat VERSION)

# Set up a known environment from the .env file
include .env

# Also include any local environment variables if .env_local exists
-include .env_local

include db-scripts.mk
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
dbshell       - Connects to the DB using pgcli : psql://${DB_USER}@${DB_HOST}/${DB_NAME}
db-clone-uat  - Clones $(DB_NAME_PROD) to $(DB_NAME_UAT) on $(DB_HOST).
                You need SSH access to $(DB_HOST) and full DB admin rights there.
db-snapshot-uat
              - Creates a snapshot of $(DB_NAME_UAT) DB as $(DB_NAME_UAT)_ss.
			    Needs SSH access to $(DB_HOST)
db-restore-uat
              - Restores a previous $(DB_NAME_UAT)_ss snapshot DB to $(DB_NAME_UAT).
			    Needs SSH access to $(DB_HOST)
db-drop-uat-snashot
              - Drops the $(DB_NAME_UAT)_ss snapshot DB created before if it exists.
			    Needs SSH access to $(DB_HOST)
db-list       - Lists all $(DB_NAME_PROD) related DBs. Needs SSH access to $(DB_HOST)
repl          - Starts a local ipython REPL with the environment set up from .env .env_local
rem-repl      - Starts REPL in container after installing ipython if not already installed
shell         - Runs bash inside the container
mr            - Generates a gitlab MR for the current branch.
                Requires glab (GitLab CLI client) to be installed and set up for repo access
show-env      - Shows the full environment the Makefile sees
docs          - Builds the documentation via pydoctor.
gen-erd       - Generates an ERD from the database into doc/ERD.md
image         - Build and push Docker image with versioned tags
test-deploy   - Tests the deployment process for the next prod deployment.
                Very helpful for testing that migrations for the next prod deployment works
                on the UAT DB.
                Normal flow is to snapshot UAT, clone UAT from prod, test deploy, restore UAT.
templates     - Compiles all HTML temlates.
deploy        - Deploys the latest release to production. Meant to be run from GL CI Pipeline.
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

# Set up the local development environment
dev-setup:
	pip install -r requirements-localdev.txt

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
# pointing to a full environment file and/or make sure that any 
# This environment file is make up from .env with .env_local overriding the
# versioned .env default values (.env_local is not versioned)
# For deployment, .env_local will be created by the GitLab CI pipeline from all
# LOC_??? variables defined as CI Variables. See .env_local_gen in
# .gitlab-ci.yml
# We dynamically create the MERGED_ENV file by cat-ing .env and .env_local into
# one temp file, copy this to the remote as a temp file, use that temp file as
# the docker startup environment, and delete the temp environment once the
# container is up.
deploy:
	@[[ -f .env && -f .env_local ]] || { echo ".env and .env_local is required"; exit 1; }
	@echo "Merging .env and .env_local to $(MERGED_ENV)..."
	@cat .env .env_local | grep -E '^[a-zA-Z0-9._]+=' > $(MERGED_ENV)
	
	@echo "Copying $(MERGED_ENV) to $(PROD_RUNTIME_ENV) on target host..."
	@scp $(MERGED_ENV) $(DEPLOY_USER)@$(DEPLOY_HOST):$(PROD_RUNTIME_ENV)
	@# When this is done, we do not need $(MERGED_ENV) anymore
	@rm -f $(MERGED_ENV)
	
	@echo "Setting runtime UID and GID into $(PROD_RUNTIME_ENV) on target host..."
	@ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "\
		echo UID=$$(id -u) >> $(PROD_RUNTIME_ENV) && \
		echo GID=$$(id -g) >> $(PROD_RUNTIME_ENV) \
	"
	
	@echo "Running deploy.py (migrations)..."
	@ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "\
		docker pull $(REGISTRY)/$(IMAGE_NAME):latest && \
		docker run --rm --env-file $(PROD_RUNTIME_ENV) \
			$(REGISTRY)/$(IMAGE_NAME):latest python deploy.py \
	"
	
	@echo "Starting service using Compose..."
	@ssh $(DEPLOY_USER)@$(DEPLOY_HOST) "\
		cd $(PROD_COMPOSE_DIR) && \
		docker compose up -d \
	"

# Tests the production deployment script - including migrations.
# The flow should be something line this:
# $ make db-snapshot-uat   # Make a snapshot of UAT if needed
# $ make db-clone-uat         # Clone prod to UAT to have a db migration test
# $ make test-deploy          # Run this test
# $ make db-restore-uat       # Return to the previous UAT snapshot
# $ make db-drop-uat-snapshot # Drop the snapshot again
#
# The migrations will by default be run for the non RC version, i.e. it strips
# _RC?? from VERSION and forces the migrations to run for that version. This
# makes it easy so that you do not have to create symlinks from RC versions to
# the deploy version migrations.
# The default is to run in DRY-RUN mode. To not run dry run, pass DRY_RUN=0 at
# the end of the make command.
test-deploy:
	docker exec -ti $(CONTAINER_NAME) env VERSION=$${VERSION%_*} DRY_RUN=$${DRY_RUN:-1} ./deploy.py
	@if [[ -z $$DRY_RUN ]]; then \
		echo -e "\nDry run is the default. To disable, run:\n    make test-migration DRY_RUN=0\n"; \
	 fi

templates:
	@./compile_templates.py

# Removes all old stopped containers to reclaim space
docker-prune:
	docker container prune

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

# Generates an ERD directly from the DB using eralchemy in a Markdown file with
# the ERD in mermaid format. The ERD is output to doc/ERD.md
# The eralchemy output is a bit weird, so we filter it through the
# er_filter.awk script. Read that for more info
gen-erd:
	@eralchemy -i postgresql://$(DB_USER):$(DB_PASS)@$(DB_HOST)/$(DB_NAME) \
		-m mermaid_er --title "Battery Capacity Meter UI ERD" -o /tmp/_erd.md && \
		./erd_filter.awk /tmp/_erd.md > doc/ERD.md && \
		rm -f /tmp_erd.md && \
		docker run --rm -u `id -u`:`id -g` -v ${PWD}/doc:/data $(MM_CLI_DOCKER) -i ERD.md -e png && \
		mv doc/ERD.md-1.png doc/img/ERD.png && \
		echo -e "Done\n\n" && \
		echo "You can remove the Mermaid CLI Docker image with:\n\n  docker image rm $(MM_CLI_DOCKER)\n"

# Connects to the DB using pgcli
# This relies on the DB_??? settings to be in the environment
dbshell:
	@# Source .env and then connect with pgcli
	@pgcli postgres://$${DB_USER}:$${DB_PASS}@$${DB_HOST}/$${DB_NAME}

# Clones the production DB to the UAT DB using the DB_NAME_UAT and DB_NAME_PROD
# names.
# The DB_SCRIPT_UAT_CLONE script is defined in db-scripts.mk
db-clone-uat:
	@echo "$$DB_SCRIPT_UAT_CLONE" | ssh $(DB_HOST) 'bash -s'

# Creates a snapshot from the UAT DB as named by DB_NAME_UAT.
# The snapshot DB name will be the UAT dn name with `_ss` appended.
# The DB_SCRIPT_SNAPSHOT_UAT script is defined in db-scripts.mk
db-snapshot-uat:
	@echo "$$DB_SCRIPT_SNAPSHOT_UAT" | ssh $(DB_HOST) 'bash -s'

# Restores the UAT DB from a previous snapshot
db-restore-uat:
	@echo "$$DB_SCRIPT_RESTORE_UAT" | ssh $(DB_HOST) 'bash -s'

# Drops the UAT snapshot DB if it exists.
db-drop-uat-snapshot:
	@echo "$$DB_SCRIPT_DROP_UAT_SNAPSHOT" | ssh $(DB_HOST) 'bash -s'

# List all $DB_NAME_PROD related DBs
db-list:
	@echo "$$DB_SCRIPT_LIST_DBS" | ssh $(DB_HOST) 'bash -s'

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

## Remote debugging helpers - see docs/DEBUGGING.md

COMP_OVRD=docker-compose.override.yml

# This is a compose template that will be created as $COMP_OVRD to allow us to
# expose the debug port for us to connect to for a debug session.
define override_template
services:
  soc-ui-dev:
    ports:
      - "$${DEBUG_PORT}:$${DEBUG_PORT}"
endef

export override_template

# Sets up for remote debugging. Make sure COMP_OVRD exists and that remote-pdb
# is installed in the container.
rem-debug-setup:
	@if [ -z "$(DEBUG_PORT)" ]; then \
		echo "Please set DEBUG_PORT in .env_local before setting up for remote debugging."; \
		exit 1; \
	fi
	@IS_RUNNING=$$(docker ps --filter "name=$(CONTAINER_NAME)" --format '{{.Names}}'); \
	echo ">>> Checking for $(COMP_OVRD)..."; \
	if [ ! -f $(COMP_OVRD) ]; then \
		echo "Creating $(COMP_OVRD)..."; \
		echo "$$override_template" > $(COMP_OVRD); \
		if [ -n "$$IS_RUNNING" ]; then \
			echo -e "\n⚠️ IMPORTANT: Please restart the container and run this again!"; \
			exit 0; \
		fi; \
	else \
		echo "$(COMP_OVRD) already exists."; \
	fi; \
	echo ">>> Checking if container '$(CONTAINER_NAME)' is running..."; \
	if [ -n "$$IS_RUNNING" ]; then \
		echo "Installing remote-pdb inside container $(CONTAINER_NAME)..."; \
		docker exec -it $(CONTAINER_NAME) pip install remote-pdb; \
	else \
		echo "Container $(CONTAINER_NAME) is not running. Please start it with 'make run'."; \
	fi

# Starts a remote debug session once a breakpoint has been hit
rem-debug:
	@echo ">>> Connecting to remote debug server on port ${DEBUG_PORT}..."
	@echo -e "See docs/DEBUGGING.md for more info.\n"
	@telnet localhost $(DEBUG_PORT)


## Shows the compose config
compose-conf:
	@docker-compose config

## Creates an MR for the current branch if not on the UAT or main branches
mr:
	@branch_name=$$(git branch --show-current); \
	if [[ $$branch_name =~ ^UAT|main$$ ]]; then \
	  echo -e "\nCan not create an MR on the UAT or main branch."; \
	  echo -e "Please create a feature branch first.\n"; \
	  exit 1; \
	fi; \
	parent=$$(./guess-parent-branch.sh); \
	if [[ -z $$parent ]]; then \
		echo -e "\nCan not determine parent branch to merge into."; \
		exit 1; \
	fi; \
	glab mr create --squash-before-merge --remove-source-branch --target-branch $$parent

## Shows the full environment the Makefile sees
show-env:
	@env

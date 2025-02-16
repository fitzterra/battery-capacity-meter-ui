
# Make sure we use bash as the shell.
SHELL := /usr/bin/env bash

REGISTRY=darwin:5000
IMAGE_NAME=bat-cap-ui
DOCKERFILE=Dockerfile
COMPOSE_FILE=docker-compose.yml

.PHONY: image dev-setup run version bump-major bump-minor bump-patch

# Get the current version from the VERSION file
VERSION := $(shell cat VERSION)

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

#
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


# Builds the docs using pydoctor. Requires the pydoctor python package to have
# been installed, and also a fully configured pydoctor.ini or similar config
# file for pydoctor
docs:
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
	html_url="$$remote_url/blob/$$branch_name/" && \
	pydoctor --project-url "$$remote_url" --html-viewsource-base "$$html_url" --template-dir=./pydoctor_templates


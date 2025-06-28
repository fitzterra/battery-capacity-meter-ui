# Makefile scripts in define statements for DB management.
# Note that these are pure Makefile syntax, so keep that in mind.
# The way this is used is to define external scripts using define statements,
# then include this file in the mail Makefile.
#
# These scripts can then be piped to bash processes in recipes instead of
# defining these inside the recipes.
#
# NOTE:
# 	Most of these scripts use direct PostgreSQL commands like, createdb,
# 	dropdb, etc., on the REMOTE DB host. This means the following requirements
# 	must be met:
# 	* These scripts needs to be piped to bash instance on the remote DB_HOST
# 	  via SSH.
# 	* In order to do this, an SSH connection to the remote must be established,
# 	  and a bash instance started, waiting for the commands to run on stdin.
# 	* The user on the remote MUST have PostgreSQL admin access and allowed to
# 	  run the various PG commands directly.
# 	* These scripts can not use the bash `read` command becase we are streaming
# 	  the script to the remote bash. If user confirmation is required, do this
# 	  on the local side because piping the script to the remote host.
# 	* Be careful with indentation in the define block. Best is to use two
# 	  spaces and not tabs. This can cause difficult to find errors. If in
# 	  doubt, remove all indentation.

# First some common unicode icons. These provides some color and nice icons to
# use for user feedback etc.
define DB_SCRIPTS_ICONS

OK="\033[0;32m✔\033[0m"
NOK="\033[0;31m✖\033[0m"
CLONE="\033[0;33m☍\033[0m"
DROP="\033[0;31m⚲\033[0m"

endef

#--------------------
# Clones the DB_NAME_PROD to DB_NAME_UAT on DB_HOST.
#
# Note:
#   * It will DROP DB_NAME_UAT before cloning from DB_NAME_PROD
#   * This can only be done if there are no open connections to either DB.
#--------------------
define DB_SCRIPT_UAT_CLONE
  set -e   # Exit on all errors
  
  $(DB_SCRIPTS_ICONS)
  
  # Drop it if it exists
  echo -e "$$DROP Dropping DB $(DB_NAME_UAT) if it exists..."
  dropdb --if-exists $(DB_NAME_UAT)
  
  # Clone it
  echo -e "$$CLONE Creating clone DB $(DB_NAME_UAT) from $(DB_NAME_PROD) ..."
  createdb -h localhost -T $(DB_NAME_PROD) $(DB_NAME_UAT)
  
  echo -e "$$OK Done."  
endef


#--------------------
# Makes a snapshot of the UAT DB to help with testing.
# The DB name to snapshot will be picked from the DB_NAME_UAT variable, and the
# snapshot name will be this DB name with `_ss` appended.
#
# Note: If the snapshot DB already exists, the script will exit with an error.
#--------------------
define DB_SCRIPT_SNAPSHOT_UAT
  set -e   # Exit on all errors
  
  $(DB_SCRIPTS_ICONS)
  
  # Generate the snapshot name and then make sure it does not already exist
  SS_DB=$(DB_NAME_UAT)_ss
  if $$(psql -c '\l' | grep -q $${SS_DB}); then
  	echo -e "$$NOK The snapshot DB $$SS_DB already exist. Remove it first."
  	exit 1
  fi
  
  echo -e "$$CLONE Creating snapshot DB: $$SS_DB from $(DB_NAME_UAT) ..."
  createdb -h localhost -T $(DB_NAME_UAT) $$SS_DB 
  
  echo -e "$$OK Done."
endef

#--------------------
# Restores the UAT DB from a previously created snapshot.
#
# Note:
# 	* Exits with an error if the snapshot does not exist
# 	* The DB_NAME_UAT DB will be dropped before the restore if it exists.
# 	* This can only be done if there are no connections open to eithe the clone
# 	  or UAT DBs.
#--------------------
define DB_SCRIPT_RESTORE_UAT
  set -e   # Exit on all errors
  
  $(DB_SCRIPTS_ICONS)
  	
  # Generate the snapshot name and then make sure it does exist
  SS_DB=$(DB_NAME_UAT)_ss
  if ! $$(psql -c '\l' | grep -q $${SS_DB}); then
  	echo -e "$$NOK The snapshot DB $$SS_DB does not exist."
  	exit 1
  fi
  
  echo -e "$$DROP dropping DB: $(DB_NAME_UAT) before restoring ..."
  dropdb --if-exists -h localhost $(DB_NAME_UAT)
  
  echo -e "$$CLONE Restoring snapshot DB $$SS_DB to $(DB_NAME_UAT) ..."
  createdb -h localhost -T $$SS_DB $(DB_NAME_UAT) 
  
  echo -e "$$OK Done."
endef


#--------------------
# Drops the snapshot DB created with DB_SCRIPT_SNAPSHOT_UAT if it exists
#--------------------
define DB_SCRIPT_DROP_UAT_SNAPSHOT
  set -e   # Exit on all errors
  
  $(DB_SCRIPTS_ICONS)
    
  # Generate the snapshot name
  SS_DB=$(DB_NAME_UAT)_ss
  
  echo -e "$$DROP dropping snapshot DB: $$SS_DB ..."
  dropdb --if-exists -h localhost $$SS_DB 
  
  echo -e "$$OK Done."
endef

#--------------------
# List all current $DB_NAME_PROD* DBs. This should show the prod and any UAT
# and snapshot DB derived from $DB_NAME_PROD.
#--------------------
define DB_SCRIPT_LIST_DBS
  set -e   # Exit on all errors
  
  psql -c '\l+ $(DB_NAME_PROD)*'
endef

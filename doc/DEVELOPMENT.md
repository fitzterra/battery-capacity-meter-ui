How to develop on this project
==============================

**Table of Content**

1. [**Import**: Using the `make` commands](#import-using-the-make-commands)
2. [Development workflow](#development-workflow)
3. [Development environment](#development-environment)
4. [Version management](#version-management)

**Import**: Using the `make` commands
---------------------------------

Most management or repetitive task are driven from the `Makefile`.

Run `make help` and _read and understand_ the available commands and use them
rather than hand crafting something.

If you find yourself repeating the same flow over and over again, add a new
recipe to the `Makefile` for this.

Development workflow
--------------------

* Check out repo
* Create GitLab Issue and/or sub tasks
* New branch off UAT for the main feature
    * Branch name format `{type}/task`, where `{type}` is one of these, but not
        limited to (createa new type when it makes sense):
        * `feature` - a new feature being developed
        * `task` - for sub tasks off a feature branch
        * `bugfix` - bugfix issue
    * Create sub branches for tasks off feature branches
    * Develop and test
    * Create MR - tasks merge back into feature branch, feature branches merge
        into UAT
* Regularly rebase feature branches onto UAT, task branches onto parent feature
    branch

Development environment
-----------------------

All config for the app is driven from environment variables that comes from
these possible sources:

* `.env`: This is the main configuration containing most runtime config values.
    Those that makes sense to give a default value will be set here.  
    * **Dev Environment**: loaded by `docker-compose.yml`
    * **Production**: Used indirectly via dynamic env file creation. See
        _Gitlab CI Variables_ below.
* `.env_local`: This is the local environment that can be used to override any
    values in `.env`.
    * **Dev Environment**: This is a physical local file created and kept in
        the dev environment. It is ignored version version management.
    * **Production**: This file will be created dynamically by the CI
        `build-image` and `deploy` pipelines from any CI variables that are
        prefixed with `LOC_`. The `LOC_` prefix is stripped off the CI variable
        name and the remainder of the name and it's value are then written to a
        build time `.env_local` file.  
        The `make deploy` command will then cat `.env` and the dynamically
        generated `.env_local` into a merged env file which is then passed to
        the docker run command as the `--env-file` command line option. This
        effectively runs the image with all environment variables set when
        starting.
* GitLab CI Variables: These are the equivalent of a `.env_local`, in that any
    `.env` var that needs to be overwritten or set at runtime, are created as
    CI variables, but the variable name must have a `LOC_` prefix, i.e to
    overwrite `DB_PASS` as a CI variable, the CI Variable name will be
    `LOC_DB_PASS`.  
    The CI pipeline will extract all `LOC_*` CI variables, and write them to a
    file called `.env_local` after stripping the `LOC_` prefix. The result in
    the pipeline is a `.local_env` than can be used by the deployment or other
    flows.

Version management
------------------

### Basic Flow

* Release to prod
* In the dev environment on the **UAT** branch, run `make release`. This will:
    * Check if there are changes on `main` not merged into `UAT` yet. If so,
        then you will be prompted to first merge `main` into `UAT`.
    * A new _release candidate_ will now be created depending on the current
        version state:
        * If this is not already and RC version, you will be prompted on
            whether to bump the major or minor version for the current release.  
            Remember that in this case, the current version will now be the
            production version, and we are now preparing for the next version,
            and will be creating `RC1` for this version.  
        * If this is already an `RC` version, the current RC version will
            automatically be bumped.
    * You will asked to confirm the new version that will be set.
    * Once confirmed, the `VERSION` file will be updated with the new `RC`
        version and committed, a tag created and all will be pushed.
    * After this a check will be made to see if there is an MR for this release
        to merge UAT into main, and if not, prompted if one should be created.
    * Now and ongoing branches can be rebased onto UAT, or new branches can be
        created from UAT.
* Once a release is ready for prod from the `main` branch, run `make release`,
    which will:
    * Check if the main branch is on an RC release.
    * If not, error out and tell you to merge `UAT` into `main` first. This
        will then bring the RC release into main.
    * If `main` is on the RC release, the RC part will be dropped from the
        version.
    * You will be prompted to confirm that the prod version is about to be
        released.
    * The version will be set, a release tag created and pushed.
    * The Gitlab deploy pipeline will now be triggered to build and deploy this
        release.
* Go to the top

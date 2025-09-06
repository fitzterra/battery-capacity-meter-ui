# Remote interactive debugging in a container

**Table of Content**

1. [Introduction](#introduction)
2. [Remote Debug Setup](#remote-debug-setup)
3. [Breakpoint Setting](#breakpoint-setting)
4. [Remote Debugging](#remote-debugging)


## Introduction

When running the application in a container during development, interactive
debugging is more difficult.

This is because it is more difficult to start the app in a console and interact
with it when a breakpoint is set.

We're talking simple `pdb` or `ipdb` here and not a complex IDE setup.

One option to get this to work is a simple remote Pdb setup using [remote-pdb].

This is debugging over a TCP socker: [remote-pdb] will listen on a socket as
soon as the breakpoint is reached. By connecting to this socket you have a
`pdb` session to the process being debugged.

The parts required:

* The container must expose the debug server port (
    see [Remote Debug Setup](#remote-debug-setup))
* The [remote-pdb] Python app should be installed in the container (
    see [Remote Debug Setup](#remote-debug-setup))
* The app should import the debugger and then set a breakpoint (
    see [Breakpoint Setting](#breakpoint-setting))
* The app should be run until the break point is encountered.
* At this point the remote debugger would instantiate the server and you can
    use telnet to connecto the port and run standard `pdb` commands.

## Remote Debug Setup

**TL;DR** run `make rem-debug-setup` and read and follow any instructions, then
see [Remote Debugging](#remote-debugging) below.

In order to not contaminate the production instance with debug stuff, all debug
setup has to be done implicitly in the dev or test environment.

The steps are:

* Add a setting for the debug port to `.env_local`.
    * `DEBUG_PORT=4444`  # or your preferred port number
    * Since this file is not versioned and the value is not defined in `.env`
        with any default value, this needs to added explicitly to `.env_local`
* Create a `docker-composer.override.yml` file that will amend the ports we
    expose to include the debug port. This file looks like this:
```
services:
  soc-ui-dev:
    ports:
      - "${DEBUG_PORT}:${DEBUG_PORT}"
```
* Docker compose will automatically amend settings in this file to the main
    compose file settings when running the container.
* Install `remote-pdb` in the running container.

This is all automated using the `rem-debug-setup` make target.

One **important** caveat:  
Once the container is stopped after `remote-pdb` was installed, that
installation will be gone the next tie the container is started. For this
reason it is important to run `make rem-debug-setup` every time after the
container has been restarted and more debugging is required.

Also note that `docker-compose.override.yml` is not versioned at the moment, so
deleting it is fine, since it can be recreated with the above command.  
Just DO NOT commit it!

## Breakpoint Setting

To set a breakpoint in the code, do the following:

```python
import os
from remote_pdb import RemotePdb

RemotePdb(
    "0.0.0.0",
    int(os.environ.get("DEBUG_PORT", 4444)),
).set_trace()
```

This will bind the remote socket to listen on all interfaces on the container
and on the `DEBUG_PORT` set in the environment, and fall back to port 4444 if
not set - although if `DEBUG_PORT` is not set, the port forwarding out of the
container will also not work.

Now run the app and wait for the breakpoint to be hit. This will be seen in the
console window monitoring the app output.
Now see [Remote Debugging](#remote-debugging) below.

## Remote Debugging

Once the breakpoint was hit, a TCP socket will be opened to which you can
connect with `telnet` or `nc`.

Easiest is to run `make rem-debug` in another terminal and you will be in the
[Pdb] session.

[Pdb] is fairly primitive but totally adequate for small scale debugging.

One **caveat**: 
When entering `c` for the process to continue running, the telnet session needs
to be exited for the same breakpoint to be hit again - this probably has
something to do with the TCP session being started in the process being
debugged and when the process finishes, the socket should be closed since
the new process would have started anew socket or some such.  
I can probably figure this out given enough brain power but it's not important
enough right now. Suffice it to say that if the telnet session is not
responding anymore, press `^[` (`Ctl-[`) to get to the telnet prompt and then
enter `q` to quit. Restart the connection again with `make rem-debug` once the
next breakpoint is hit.

<!-- links -->
[remote-pdb]: https://github.com/ionelmc/python-remote-pdb
[Pdb]: https://docs.python.org/3/library/pdb.html

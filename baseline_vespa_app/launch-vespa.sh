#!/bin/bash

# wait for vespa config server to launch and launch content server in the background
/wait-for-config-server.sh &

# container-local script for launching entry-point
/usr/local/bin/start-container.sh


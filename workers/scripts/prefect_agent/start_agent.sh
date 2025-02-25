#!/bin/bash
set -e

# Start the Prefect agent
prefect agent start -q "userport-workers"
#!/bin/bash
# EC2 user data (runs once at first boot, as root).
# Hard cost cap: the OS shuts down after 10 hours no matter what. The instance is
# launched with shutdown behaviour "stop", so results on disk survive and only the
# EBS volume (cents per day) keeps billing until it is terminated.
shutdown -h +600 "pdw: 10-hour cost cap reached"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-venv python3-pip git tmux
touch /var/tmp/pdw-userdata-done

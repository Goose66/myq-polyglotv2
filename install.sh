#!/usr/bin/env bash

# package install requirements for Polisy (FreeBSD)
if [ -f /usr/local/etc/pkg/repos/udi.conf ]; then
  pkg install -y libxml2
  pkg install -y libxslt
# package install requirements for Raspbian (Debian)
else
  sudo apt-get install python3-pyquery --quiet --yes
fi

pip3 install -r requirements.txt --user

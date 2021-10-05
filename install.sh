#!/usr/bin/env bash

# package install requirements for Polisy (FreeBSD)
if [ -f /usr/local/etc/pkg/repos/udi.conf ]; then
  sudo pkg install libxml2
  sudo pkg install libxslt
# package install requirements for Raspbian (Debian)
else
  sudo apt-get install python3-pyquery --quiet --yes
fi

pip3 install -r requirements.txt --user
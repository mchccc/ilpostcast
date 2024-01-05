#!/bin/sh

case "$OSTYPE" in
  darwin*)  echo "OSX"; export ARCH="macos-aarch64" ;;
  linux*)   echo "LINUX"; export ARCH="linux-aarch64" ;;
  *)        echo "unknown: $OSTYPE" ;;
esac

REPO="mozilla/geckodriver"; \
curl -s https://api.github.com/repos/${REPO}/releases/latest | grep "browser_download_url.*`echo $ARCH`"\
| head -1 \
| cut -d : -f 2,3 \
| tr -d \" \
| wget --show-progress -qi - -O -\
| tar -xzvf - -C /bin

#!/usr/bin/env bash
sudo apt-get update
sudo apt-get -y install docker.io python3-venv

#install the testbed:
python3 -m venv venv
source venv/bin/activate
pip install -r setup/requirements.txt
deactivate
sudo chmod -R 777 .


#install the tools:

sudo docker pull cryptomental/maian-augur-ci
sudo docker pull trailofbits/manticore
sudo docker pull mythril/myth
sudo docker pull christoftorres/osiris
sudo docker pull luongnguyen/oyente
sudo docker build -t securify https://github.com/eth-sri/securify2.git
sudo docker build -t smartcheck setup/

#install solc compiler:
mkdir -p resources/solc-versions/

LAST_MINOR_VERSION_AVAILABLE="not available"
MAJOR_VERSION=4
MINOR_VERSION=0
while true; do
    VERSION="0.$MAJOR_VERSION.$MINOR_VERSION"
    SOLC_DIR=resources/solc-versions/$VERSION
    mkdir $SOLC_DIR
    SOLC_BIN_PATH=$SOLC_DIR/solc-static-linux
    wget -P $SOLC_DIR https://github.com/ethereum/solidity/releases/download/v$VERSION/solc-static-linux &> /dev/null
    if [[ $? -eq 0 ]]; then
      sudo chmod 777 $SOLC_BIN_PATH
      mv $SOLC_BIN_PATH $SOLC_DIR/solc
      LAST_MINOR_VERSION_AVAILABLE=available
      echo installed version $VERSION to $SOLC_DIR/solc
      ((MINOR_VERSION++))
    else
      # version is not available
      sudo rm -R $SOLC_DIR
      # check whether we have already downloaded the newest version
      if [ "$MAJOR_VERSION" -gt 8 ] && [ "$MINOR_VERSION" == 0 ]; then
        echo "Installed all available versions."
        break
      fi
      if [ "$LAST_MINOR_VERSION_AVAILABLE" == "available" ]; then
        # The latest minor version of the current major version is already installed.
        ((MAJOR_VERSION++))
        MINOR_VERSION=0
      else
        # The current minor version is not available on GitHub anymore. Try the next minor version...
        ((MINOR_VERSION++))
      fi
      LAST_MINOR_VERSION_AVAILABLE="not available"
    fi
done
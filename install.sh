#!/bin/bash

[ "$(basename $(pwd))" == "cosmos-env" ] || { echo "must be run from cosmos-env directory" ; exit 1 ; }
[ -z $(which python3) ] && { echo "python3 required" ; exit 1 ; }
[ -z $(which git) ] && { echo "git required" ; exit 1 ; }
[ -z $(which lxd) ] && { echo "lxd required" ; exit 1 ; }
[ -z $(which jq) ] && { echo "jq required" ; exit 1 ; }

rm -rf ~/.cosmos-env && mkdir ~/.cosmos-env
for i in $(ls); do
  [ "$i" != "install.sh" ] && [ "$i" != "README.md" ] && cp -r $i ~/.cosmos-env/
done
chmod +x ~/.cosmos-env/{cosmwasm/upload,cosmos-go/init_node}
[ -z "$(grep ". ~/.cosmos-env/load" ~/.bashrc)" ] && echo -e ". ~/.cosmos-env/load" >> ~/.bashrc

source ~/.bashrc
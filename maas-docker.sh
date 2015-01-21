#!/bin/sh

base="ubuntu:latest"
image="okffi/maas"
maascmd="server/run.sh"

# TODO: add persistent data container for postgres separate from the code container http://stackoverflow.com/questions/18496940/how-to-deal-with-persistent-storage-e-g-databases-in-docker

usage() {
    echo "Usage: $0 {create|update|updateall|show|build|run|stop} [options]"
    echo ""
    echo "Utility script for docker-packaged MaaS API Server."
    echo "Requires that packer and docker are properly installed (See https://packer.io/ or https://docs.docker.com/#installation-guides)"
    echo ""
    echo "Commands:"
    echo "  create              creates MaaS API Server docker image ($image) from ($base) and imports it into local repository"
    echo "  update              updates MaaS API Server files from current durectory (copies server folder into /maas/server in the docker container)"
    echo "  updateall           updates operating system and MaaS API Server within docker image"
    echo "  shell               runs docker container in interactive mode with a shell"
    echo "  show                displays installed maas images and running containers"
    echo "  list                same as show"
    echo "  start [port]        runs MaaS API Server at a specified TCP port on the host system"
    echo "  run [port]          same as start"
    echo "  stop <containerID>  stops a running container with containerID (first column in 'show' command output)"
}

rc=255
case "$1" in
	create)
		packer build -color=false -var "base_image=$base" -var "maas_image=$image" maas-create.json
		;;
	update)
		packer build -color=false -var "base_image=$image" -var "maas_image=$image" maas-update.json
		;;
	updateall)
		packer build -color=false -var "base_image=$image" -var "maas_image=$image" maas-updateos.json
		packer build -color=false -var "base_image=$image" -var "maas_image=$image" maas-update.json
		;;
	shell)
		docker run -w /maas -it "$image" /bin/bash
		;;
  list|show)
		echo "\nIMAGES:"
		docker images | grep "$image"
		echo "\nCONTAINERS (running docker instances):"
		docker ps | grep "$image"
		;;
	start|run)
		port=80
		if [ "$2" != "" ]; then
		    port=$2
		fi
		docker run -d -w /maas -p $port:8080 "$image" $maascmd 8080
		rc=$?
		;;
	stop)
		if [ "$2" = "" ]; then
		    usage
		    exit 1
		fi
		docker stop "$2"
		rc=$?
		;;
	*)
		usage
		rc=1
		;;
esac
exit $rc

#!/usr/bin/env bash

DOCKER=docker

${DOCKER} build cicd -f cicd/Dockerfile_sonar --tag pybutcherbackup-sonar

${DOCKER} run -it --rm --name pybutcherbackup-sonar -e SONAR_LOGIN=${SONAR_LOGIN} -v "$PWD":/usr/src/myapp -w /usr/src/myapp pybutcherbackup-sonar  "./cicd/run_analyze.sh"

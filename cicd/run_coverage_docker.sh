#!/usr/bin/env bash

DOCKER=docker

cp requirements.txt cicd/requirements.txt
${DOCKER} build cicd -f cicd/Dockerfile_python --tag pybutcherbackup-python
rm cicd/requirements.txt

${DOCKER} run --rm --name pybutcherbackup-python -v "$PWD":/usr/src/myapp -w /usr/src/myapp pybutcherbackup-python  "./run_coverage.sh"

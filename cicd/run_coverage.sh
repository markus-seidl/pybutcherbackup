#!/usr/bin/env bash

# Assumes this script runs in the root directory directly.

# source ./venv/bin/activate

COVERAGE=coverage3

cd ..

mkdir "./results"
rm -rf ./results/*

${COVERAGE} erase
${COVERAGE} run --source=backup -m xmlrunner discover -v -o "./results/"
${COVERAGE} report
${COVERAGE} xml -i -o "./results/coverage.xml"


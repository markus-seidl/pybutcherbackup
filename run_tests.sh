#!/bin/bash

source ./venv/bin/activate

PYTHON=./venv/bin/python3

rm -rf ./results/*
${PYTHON} -m xmlrunner discover -v -o "./results/"


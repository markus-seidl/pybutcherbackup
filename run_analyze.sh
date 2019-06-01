#!/usr/bin/env bash

source ./venv/bin/activate

COVERAGE=coverage3
SONAR_SCANNER=sonar-scanner

mkdir "./results"
rm -rf ./results/*

${COVERAGE} erase
${COVERAGE} run --source=backup -m xmlrunner discover -v -o "./results/"
${COVERAGE} report
${COVERAGE} xml -i -o "./results/coverage.xml"

${SONAR_SCANNER} \
  -Dsonar.projectKey=pybutcherbackup \
  -Dsonar.sources=. \
  -Dsonar.host.url=https://sonar.markus-seidl.de \
  -Dsonar.login=${SONAR_LOGIN} \
  -Dsonar.python.coverage.reportPaths="results/*coverage*.xml" \
  -Dsonar.python.xunit.reportPath="results/TEST-*.xml" \
  -Dsonar.test.exclusions="./tests/*"

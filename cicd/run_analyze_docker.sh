#!/usr/bin/env bash

COVERAGE=coverage3
SONAR_SCANNER=sonar-scanner

${SONAR_SCANNER} \
  -Dsonar.projectKey=markus-seidl_pybutcherbackup \
  -Dsonar.organization=markus-seidl \
  -Dsonar.sources=. \
  -Dsonar.host.url=https://sonar.markus-seidl.de \
  -Dsonar.login=${SONAR_LOGIN} \
  -Dsonar.python.coverage.reportPaths="results/*coverage*.xml" \
  -Dsonar.python.xunit.reportPath="results/TEST-*.xml" \
  -Dsonar.test.exclusions="./tests/*"

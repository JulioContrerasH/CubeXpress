#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

poetry version patch
poetry version
rm -rf dist
poetry build
ls dist

git add .
git commit -m "cubexpress: up"
git push origin main

poetry publish

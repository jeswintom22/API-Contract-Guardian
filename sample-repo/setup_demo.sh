#!/bin/bash
# Run once from inside sample-repo/ to set up the demo history:
# a `main` branch (working API) and a `breaking-change` branch
# where total_amount -> total on the /checkout response.
set -e

git init
git checkout -b main
git add .
git commit -m "Base: working checkout API"

git checkout -b breaking-change

# The actual breaking change: rename total_amount -> total.
# Deliberately does NOT touch consumers/, tests/, or README.md —
# that's the whole point of the demo.
sed -i 's/total_amount/total/g' app/main.py

git add app/main.py
git commit -m "Rename total_amount to total on /checkout response"

echo "Done. Branches: main (before), breaking-change (after)."
echo "Run Guardian with base_ref=main head_ref=breaking-change"

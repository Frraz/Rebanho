#!/bin/bash

find . -type f \( \
    -name "*.py" -o \
    -name "*.html" -o \
    -name "*.css" -o \
    -name "*.js" -o \
    -name "*.txt" -o \
    -name "*.sh" -o \
    -name "*.yml" \
\) \
-not -path "*/.venv/*" \
-not -path "*/venv/*" \
-not -path "*/__pycache__/*" \
-not -path "*/node_modules/*" \
-not -path "*/staticfiles/*" \
| sed "s|^\./||"

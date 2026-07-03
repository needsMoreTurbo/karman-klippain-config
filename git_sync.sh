#!/bin/bash
cd ~/printer_data/config

if [ "$1" == "pull" ]; then
  git pull origin main
elif [ "$1" == "push" ]; then
  git add .
  git commit -m "Auto-commit from printer: $(date +'%Y-%m-%d %H:%M:%S')"
  git push origin main
fi

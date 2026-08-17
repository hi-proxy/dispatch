#!/bin/zsh

print -r -- "FUNGIS_E2E_READY"
while IFS= read -r line; do
  print -r -- "FUNGIS_E2E_RECEIVED:${line}"
done

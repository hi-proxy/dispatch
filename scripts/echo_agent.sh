#!/bin/zsh

print -r -- "DISPATCH_E2E_READY"
while IFS= read -r line; do
  print -r -- "DISPATCH_E2E_RECEIVED:${line}"
done

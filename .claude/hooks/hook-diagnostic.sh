#!/bin/bash
# Diagnostic hook — writes timestamp + trigger info to a log file.
# Used to verify whether Claude Desktop actually fires hooks.
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | HOOK FIRED | trigger=$1 | cwd=$(pwd)" >> .claude/hooks/hook-diagnostic.log

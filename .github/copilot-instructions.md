# PiGenus repository instructions

PiGenus is the Raspberry Pi based core node of the GENUS system.

## Goal
Build PiGenus as a small but complete operational core.

## Priorities
- stability over ambition
- persistence over temporary output
- simple modular structure
- minimal dependencies
- Raspberry Pi friendly

## Current target
Implement PiGenus v0.1:
- orchestrator
- task queue
- persistent memory
- problem matrix
- agent matrix
- matcher
- basic worker
- evaluator
- restart support

## Non-goals
Do not implement:
- swarm scaling
- reinforcement learning
- heavy local models
- UI
- plugins
- self-modifying code

## Runtime
- Python 3
- low resources
- no GPU assumptions

## Persistence
Must store:
- state.json
- task_ledger.json
- agent_ledger.json
- queue.json
- events.log

## Rule
A working small loop is more important than a big unfinished system.

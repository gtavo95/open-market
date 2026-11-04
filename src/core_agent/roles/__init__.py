"""The roles: each one with its table, its judge and its cell. What the model reads is in `prompts/`.

One file per role and none imports another, except `writer`, which reads the
sale's line and the effects' line because its request carries them. Who
composes them is `agent.py`; nobody here knows in what order they run.
"""

"""Shared code of the thesis pipeline (wildfire detection latency from EO satellites).

Modules:
    paths        every input and output location (one place; scripts never build paths themselves)
    registry     events_registry.yaml and the hand-edited ground-truth table of the candidates
    geo          boxes, distances, clustering, map projection
    plotting     figure style, basemap and tile cache
    schema       shared observation schema v2 and checked writers
    orbits       swaths, passes over a point, elevation mask, Terra relay wait
    firms        FIRMS clean tables and the per-event FIRMS selection
    lsasaf       LSA SAF regions (SEVIRI disk)
    effis        EFFIS record sets and the FIRMS outputs they are checked against
    credentials  account credentials (environment first, then the .env file)
    spacetrack   Space-Track session
    s0           S0 detection sources, official perimeters and the T0 rule
    s1           S1 simulator run: passes, contacts and time to ground
"""

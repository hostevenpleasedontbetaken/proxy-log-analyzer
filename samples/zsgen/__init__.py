"""Behaviour-simulation generator for Zscaler NSS web logs.

world.py    the fictional company: users, devices, habits, websites
traffic.py  normal browsing over time (page loads, assets, policy blocks)
lookalikes.py  benign traffic that looks suspicious (agents, IT scripts, big uploads)
scenarios.py   planted attacks, each labelled for the answer key
answer_key.py  the *.ground_truth.json file: which record ids are which attack
request.py  one simulated web request, before it's written out
zscaler.py  turns a request into a Zscaler v12 NDJSON line
"""

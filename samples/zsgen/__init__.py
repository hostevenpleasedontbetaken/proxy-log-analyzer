"""Behaviour-simulation generator for Zscaler NSS web logs.

world.py    the fictional company: users, devices, habits, websites
traffic.py  normal browsing over time (page loads, assets, policy blocks)
request.py  one simulated web request, before it's written out
zscaler.py  turns a request into a Zscaler v12 NDJSON line
"""

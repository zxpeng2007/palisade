"""Shared test configuration.

The credential rate limit (burst 5 per address) exists to make online
password guessing expensive; the test suite registers dozens of accounts
from one client, so it is opened wide here. The moves bucket keeps its real
values — no test comes near 10 moves/second.
"""

from murus import limits

limits.credentials.burst = 100000.0
limits.credentials.rate = 100000.0

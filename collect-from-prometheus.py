#!/usr/bin/python
#
# Collect inventory from Prometheus.
# Run with:
#   export PROMCRED=<user>:<password>
#   python collect-from-prometheus.py -v -v  -u https://your-prometheus-1  -v --hide-ignored
#
# (c) 2019, Nuno Tavares <n.tavares@portavita.eu>
#

from PrometheusInventory import PrometheusInventory

if __name__ == "__main__":
    ARGS = PrometheusInventory.parse_options()
    runner = PrometheusInventory(ARGS)
    runner.run()
    runner.print_results()

Purpose:
collects hardware inventory data from Prometheus based on a rules file (configmap-prom-inventory.yaml) which describes how to parse metrics and its labels.

The metrics you'll see in configmap-prom-inventory.yaml are being produced with the following exporters:
- snmp-exporter
- node_exporter textfile collector: dmidecode.py - https://github.com/prometheus-community/node-exporter-textfile-collector-scripts/pull/42
- node_exporter textfile collector: storcli.py
- node_exporter textfile collector: hpssacli.pl - https://github.com/prometheus-community/node-exporter-textfile-collector-scripts/pull/4
- node_exporter textfile collector: tw_cli.py

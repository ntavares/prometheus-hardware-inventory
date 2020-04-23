import unittest
from unittest.case import SkipTest

from PrometheusInventory import PrometheusInventory


class PrometheusInventoryTests(unittest.TestCase):

    def setUp(self):
        ARGS = PrometheusInventory.parse_options()
        # Enforce removal of ignored records
        ARGS.hide_ignored = True
        # Remove rules that can cause problems
        ARGS.exception = 'disk:smartmon'
        self.runner = PrometheusInventory(ARGS)

        self.endpoints = [
            'https://your.prometheus.endpoint.net',
        ]
        pass

    def test_current_config_against_all_stacks_no_duplicate_serial(self):
        for ep in self.endpoints:
            self.runner.options.prom_endpoint = ep
            self.runner.run()

        index = {}
        for row in self.runner.DB:
            idxkey = row['location'] + '&:&' + row['serial']
            if idxkey in index:
                self.runner.debug(1, 'found duplicate: serial=' + str(row['serial']) + ', location=' + str(row['location']) + '\n'
                                     'previous.sources: ' + str(row['sources']) + '\n'
                                     'current.sources: ' + str(index[idxkey]))
            self.assertTrue(idxkey not in index)
            index.update({idxkey: row['sources']})


    def test_joins(self):
        raise SkipTest('TODO - Not implemented.')



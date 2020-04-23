import unittest
import test_common
import fixtures_input

from nose.plugins.attrib import attr

from PrometheusInventory import PrometheusInventory

@attr('online')
@attr('input')
class PvUsrMgrInputTests(fixtures_input.PromInvInputTests):

    def setUp(self):
        self.context = test_common.TestContextOnline()
        self.runner = PrometheusInventory( self.context.get_options() )

        self.endpoints = [
            'https://your-prometheus-1.net',
            'https://your-prometheus-2.net',
            'https://your-prometheus-3.net',
        ]



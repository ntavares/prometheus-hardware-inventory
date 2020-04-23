import unittest

import test_common
import fixtures_input

from nose.plugins.attrib import attr

from PrometheusInventory import PrometheusInventory

import json

TESTDATA_FOLDER='./tests/data'

@attr('offline')
@attr('input')
class PvUsrMgrInputTests(fixtures_input.PromInvInputTests):


    def mocked_get_results(self, entry):
        with open(TESTDATA_FOLDER + '/' + entry['metric'] + '.json') as json_file:
            return json.load(json_file)

    def setUp(self):
        self.context = test_common.TestContextOffline()
        self.runner = PrometheusInventory( self.context.get_options() )
        self.runner.get_results = self.mocked_get_results


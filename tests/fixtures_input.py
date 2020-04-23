
import unittest
from unittest.case import SkipTest



#
# NOTE: most of these tests are top-level (full-flow). We maybe should test specific API calls instead, but..?
#
class PromInvInputTests(unittest.TestCase):

    def test_current_config_against_all_stacks_no_duplicate_serial(self):
        if self.context.mode not in ['online']:
            raise SkipTest('Online test only.')

        for ep in self.endpoints:
            self.runner.options.prom_endpoint = ep
            self.runner.run()

        index = {}
        print('DB = ' + str(self.runner.DB))
        for row in self.runner.DB:
            idxkey = row['location'] + '&:&' + row['serial']
            if idxkey in index:
                self.runner.debug(1, 'found duplicate: serial=' + str(row['serial']) + ', location=' + str(row['location']) + '\n'
                                     'previous.sources: ' + str(row['sources']) + '\n'
                                     'current.sources: ' + str(index[idxkey]))
            self.assertTrue(idxkey not in index)
            index.update({idxkey: row['sources']})

    def test_join_lookups(self):
        self.runner.run()
        # Use nosetests -s ... to see the print
        self.runner.print_results()
        cs7048t = 0
        for row in self.runner.DB:
            if row['model'] == 'DCS-7048T-A':
                cs7048t += 1
        self.runner.debug(1, 'DCS-7048T-A count. ' + str(cs7048t))
        self.assertTrue(cs7048t == 1)

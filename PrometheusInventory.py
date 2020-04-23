#!/usr/bin/env python3
#
# Collect inventory from Prometheus.
#
# (c) 2020, Nuno Tavares <n.tavares@portavita.eu>
#
from __future__ import print_function

import pprint
import os.path
import sys
import requests
import json
import re
from prettytable import PrettyTable
import argparse

import yaml
import datetime

DESCRIPTION = """Collects inventory data from Prometheus"""
VERSION = '0.0.1'


class PrometheusInventory:

    MAP = None
    DEBUG = 0
    MSGFD = None
    options = None
    DB = []
    FILTER = {}
    EXCLUSION = {}
    CACHE = {}

    last_error = None

    def __init__(self, options):
        self.DB = []
        self.CACHE = {}
        self.options = options
        if os.environ.get('KUBERNETES_PORT'):
            self.MSGFD = sys.stdout
        else:
            #self.MSGFD = sys.stderr
            self.MSGFD = sys.stdout

        filter = self.options.filter.split(',')
        exclusion = self.options.exclude.split(',')
        if len(self.options.filter)>0:
            for f in filter:
                k,v = f.split('=')
                self.FILTER.update( {k: v} )
        elif len(self.options.exclude)>0:
            for f in exclusion:
                k,v = f.split('=')
                self.EXCLUSION.update( {k: v} )

        # skip-ssl: For requests >= 2.16.0
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # skip-ssl: For requests < 2.16.0
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

        # https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
        #yaml.warnings({'YAMLLoadWarning': False})

        return

    def getTimestamp(self):
        return str(datetime.datetime.now()).split('.')[0]

    def getDebug(self):
        return self.options.debug

    def setDebug(self, d):
        self.options.debug = d

    def get_last_error(self):
        return self.last_error

    def info(self, args):
        print("[i] " + args)

    def error(self, args):
        self.last_error = args
        print("[ERROR] " + args)

    def debug(self, level, args):
        if self.getDebug()>=level:
            print("[D:" + str(level) + "] " + args, file=self.MSGFD)

    def debug_var(self, level, arg):
        if self.getDebug()>=level:
            self.debug( level, pprint.pformat(arg) )

    def load_config(self):
        with open(self.options.config) as f:
            self.MAP = yaml.load(f)

    def push_row(self, r, targetDb):
        # check for duplicates - this block could well be very specific.... and turn out to be very difficult
        if r['collisions'] in ['override']:
            updated = False
            for dr in targetDb:
                if dr['type'] == r['type'] and dr['model'] == r['model'] and dr['location'] == r['location']:
                    if dr['brand'] == '' and r['brand'] != '':
                        self.debug(4, "     [push_row] collision in brand:\ndr=" + str(dr) + "\nr=" + str(r))
                        dr['brand'] = r['brand']
                        if r['sources'] not in dr['sources']:
                            dr['sources'] += r['sources']
                        updated = True
                    if dr['serial'] == '' and r['serial'] != '':
                        self.debug(4, "     [push_row] collision in serial\ndr=" + str(dr) + "\nr=" + str(r))
                        dr['serial'] = r['serial']
                        if r['sources'] not in dr['sources']:
                            dr['sources'] += r['sources']
                        updated = True
                    if updated:
                        return
        self.debug(4, "   [push_row] adding: " + str(r))
        targetDb += [ r ]

    def check_if_ignore(self, row, m):
        for ignrule in m['ignore_regexp']:
            self.debug(4, '   [check_if_ignore] ignrule: ' + str(ignrule) + ', against: ' + str(row['metric']))
            for ignfield, ignexp in ignrule.items():
                # special case, when we want to match missing labels (as we cannot match against, e.g., the empty content because it's missing)
                if not ignexp and ignfield not in row['metric']:
                    self.debug(4, '   [check_if_ignore] ignrule matched!')
                    return True
                if ignfield in row['metric'] and ignexp and re.match(ignexp, row['metric'][ignfield]):
                    #self.debug(3, '   [check_if_ignore] ignrule matched!')
                    return True
        self.debug(4, '   [check_if_ignore] ignrule did not match!')
        return False

    def get_uri(self, entry):
        return self.options.prom_endpoint + '/api/v1/query?query=' + entry['metric']

    def get_results(self, entry):
        if entry['metric'] in self.CACHE:
            self.debug(2, ' [get_results] returning cached results for: ' + entry['metric'])
            return self.CACHE[entry['metric']]
        uri = self.get_uri(entry)
        self.debug(2, ' [get_results] querying: ' + str(uri))
        if 'PROMCRED' in os.environ:
            xu, xp = os.environ['PROMCRED'].split(':')
            r = requests.get(uri, verify=False, auth=(xu, xp))
        else:
            r = requests.get(uri, verify=False)
        if r.status_code != 200:
            return {'status': 'http code: ' + str(r.status_code)}
        self.CACHE[entry['metric']] = json.loads(r.content.decode('UTF-8'))
        return self.CACHE[entry['metric']]

    """
    row will contain, among the "data" that we're looking for, also some metafields that should be locatable via
    idxlist, in the form: for idx in idxlist: row['_index_' + idx]
    """
    def __gen_index_key(self, row, idxlist, lblprefix = '_index_'):
        idxvals = []
        for idx in idxlist:
            idxvals += [ row[lblprefix + idx] ]
        return '-'.join(idxvals)

    """
    This function will assemble a dict whose keys are the relevant labels we which to obtain from the join (aka lookup),
    according to the mapping specified in the config (e.g.: _brand = entPhysicalMfgName), and values will be an indexed
    map/dict of "the index fields concatenated by '-'" and the respective value.
    This is so we can support multiple index fields, for precise correlation.
    
    The actual gathering of the values happens with lookupstmp, where the index fields are acquired by extending the 
    labels definition with our own private mapping, by injecting labels such as '_index_' + index (for each index field).
    This way we preserve those values after process() is called, to be used in the reordering afterwards.
    """
    def build_lookups(self, m):
        lookupstmp = {}
        for join in m['join']:
            self.debug(3, '  [build_lookups] for: ' + join['metric'] + ' using index: ' + str(join['index']))
            self.complete_with_defaults(join)
            # pushdown filters?
            join['ignore_regexp'] += m['ignore_regexp']

            skip_fields = ['extra']
            for idx in join['index']:
                # Because we'll be using process() to collect this metric, we need to make sure that the 'index' fields
                # are preserved (so we can use them later)
                join['labels']['_index_' + idx] = idx
                skip_fields += ['_index_' + idx]
            #self.debug(3, 'join = ' + str(join))
            #self.debug(3, "join['labels']['__index__'] = join['index'] = " + str(join['index']))
            for field in join['labels'].keys():
                if field in skip_fields:
                    continue
                lookupstmp[field] = []
                self.process(join, lookupstmp[field])
                self.debug(3, '  [build_lookups] this lookup (' + field + ') has ' + str(len(lookupstmp[field])) + ' elements.')
        self.debug(3,'lookupstmp = ')
        self.debug_var(3, lookupstmp)

        #self.debug(2, 'm[join] = ')
        #self.debug_var(2, m['join'])

        # reorganize lookups by 'index'
        lookups = {}
        for join in m['join']:
            self.debug(3, '  [build_lookups] reindexing: ' + join['metric'])
            for field in join['labels']:
                if field in skip_fields:
                    continue
                self.debug(3, 'field is relevant in join[labels]=' + field)
                lookups[field] = { 'index': join['index'], 'metric': join['metric'], 'data': {} }
                for row in lookupstmp[field]:
                    if field in row:
                        lookups[field]['data'][ self.__gen_index_key(row, join['index']) ] = row[field]
                    else:
                        lookups[field]['data'][ self.__gen_index_key(row, join['index']) ] = ''
        del lookupstmp
        return lookups


    def process(self, m, targetDB):
        self.debug(1, '[process] processing entry=' + m['metric'] + ", labels=" + str(m['labels']))

        # First, we get the metrics to join, so we can use them as lookups
        lookups = self.build_lookups(m)
        self.debug(3,'lookups = ')
        self.debug_var(3, lookups)

        """ We need to preserve, in the main metric, all index fields we find in joins, so that we can use them later
        to correlate with the lookups, so let's inject them in the same form
        """
#        idxfields = []
#        for join in m['join']:
#            idxfields += join['index']
#        idxfields = list(set(idxfields))
#        self.debug(3, 'injecting index fields as labels to preserve from the metric: ' + str(idxfields))
#        for idxfield in idxfields:
#            m['labels'].update({'_index_' + idxfield: idxfield } )
#        self.debug(3, 'now m.labels looks like: ' + str(m['labels']))

        rj = self.get_results(m)
        #self.debug_var(2, rj)

        if rj['status'] != 'success':
            self.error('Prometheus query failed for metric [' + m['metric'] + ']: ' + rj['status'])
            return None
        for row in rj['data']['result']:
            #self.debug_var(2, row['metric'])
            #self.debug_var(2, m['labels'])
            irow = { 'type': m['type'], 'brand':'', 'model':'', 'serial':'', 'location':'', 'extra': [], 'sources': [ m['metric'] ], 'collisions': m['collisions']}

            # Inject the lookups as original metric's labels, so we can refer to them as if they were there from the beginning.
            # This allows for lookup data to be injected as 'extra' (this field is ignored during lookups building, which makes it
            # impossible to be passed in join[].label)
            for field in lookups:
                index = lookups[field]['index']
                self.debug(4, 'checking field: ' + field + ', joining_row: ' + str(row))
                #self.debug_var(2, lookups[field]['data'])

                rowidx = self.__gen_index_key(row['metric'], lookups[field]['index'], '')
                if rowidx in lookups[field]['data']:
                    row['metric'][field] = lookups[field]['data'][rowidx]
                    irow['sources'] += [lookups[field]['metric']]

            for l in row['metric']:
                for tl, tv in m['labels'].items():
                    if (tl != 'extra') and (type(tv) is list):
                        for tv2 in tv:
                            if l == tv2:
                                irow[tl] = row['metric'][l]
                    else:
                        if (tl != 'extra') and (l == tv):
                            #self.debug(2, ' + matched: ' + tl + ' = ' + row['metric'][l])
                            irow[tl] = row['metric'][l].strip()
                if l in m['labels']['extra']:
                    irow['extra'] += [ row['metric'][l] ]


            #self.debug(3, "regexp = " + str(m['regexp']))
            for f, exp in m['regexp'].items():
                if f in row['metric']:
                    r = re.match(exp, row['metric'][f] )
                    if r:
                        for lk, lv in r.groupdict().items():
                            irow[lk] = lv
            for f, v in m['static'].items():
                irow[f] = v

            if self.check_if_ignore(row, m):
                if self.options.hide_ignored:
                    continue
                irow['extra'] += [ 'ignored' ]
                irow['ignored'] = True
#            else:
#                for field in lookups:
#                    if field in ['__index__']:
#                        continue
#                    index = lookups[field]['index']
#                    #self.debug(2, 'checking field: ' + field + ', joining_row: ' + str(row))
#                    #self.debug_var(2, lookups[field]['data'])
#                    if row['metric'][index] in lookups[field]['data']:
#                        if isinstance(irow[field], list):
#                            irow[field] += [ lookups[field]['data'][ row['metric'][index] ] ]
#                        else:
#                            irow[field] = lookups[field]['data'][ row['metric'][index] ]

            # for non-recursive (ie, parent entries), log the source entry (for debugging)
            if 'name' in m:
                irow['sources'].insert(0, m['name'])
            self.push_row(irow, targetDB)

    def complete_with_defaults(self, m):
        m['ignored'] = False
        if not 'collisions' in m:
            m['collisions'] = 'override'
        if not 'static' in m:
            m['static'] = {}
        if not 'regexp' in m:
            m['regexp'] = {}
        if not 'ignore_regexp' in m:
            m['ignore_regexp'] = []
        # following are required: type, labels
        if not 'extra' in m['labels']:
            m['labels']['extra'] = [ ]
        if not 'join' in m:
            m['join'] = {}
        # added to support join/lookups
        if not 'type' in m:
            m['type'] = 'unknown'

    def get_filtered_results(self):
        for r in self.DB:
            finclude = True
            if len(self.FILTER) != 0:
                for fk, fv in self.FILTER.items():
                    if r[fk] != fv:
                        finclude = False
            elif len(self.EXCLUSION) != 0:
                for fk, fv in self.EXCLUSION.items():
                    if r[fk] == fv:
                        finclude = False
            if finclude:
                yield r


    def print_results(self):
        if self.options.show_sources:
            tbl = PrettyTable(["Type", "Brand", "Model", "Serial", "Location/Owner", "Extra", "Sources"])
        else:
            tbl = PrettyTable(["Type", "Brand", "Model", "Serial", "Location/Owner", "Extra"])
        for r in self.get_filtered_results():
            if self.options.show_sources:
                tbl.add_row([ r['type'], r['brand'], r['model'], r['serial'], r['location'], ';'.join(r['extra']), ','.join(r['sources']) ])
            else:
                tbl.add_row([ r['type'], r['brand'], r['model'], r['serial'], r['location'], ';'.join(r['extra']) ])

        print(tbl)


    def run(self):
        self.debug(1, 'Debug level: ' + str(self.getDebug()))
        self.debug(1, 'Config: ' + self.options.config)
        self.debug(1, 'Endpoint: ' + self.options.prom_endpoint)
        self.load_config()
        #self.debug_var(3, self.MAP)
        for metric in self.MAP['map']:
            process_metric = False
            if len(self.options.only) <= 0:
                if (len(self.options.exception) <= 0):
                    process_metric = True
                else:
                    if metric['name'] != self.options.exception:
                        process_metric = True
            else:
                if metric['name'] == self.options.only:
                    process_metric = True

            if process_metric:
                self.complete_with_defaults(metric)
                self.process(metric, self.DB)
            else:
                self.debug(1, 'Skipping name "' + str(metric['name']) + '" for not being included with --only: ' + str(self.options.only))
                continue

        return

    @staticmethod
    def parse_options():
        PARSER = argparse.ArgumentParser(
            description=DESCRIPTION, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        PARSER.add_argument(
            '--config', default='./configmap-prom-inventory.yaml', dest='config', help='path to ConfigMap')
        PARSER.add_argument(
            '-v', default=0, dest='debug', action='count', help='Verbosity (repeat to increase level)')
        PARSER.add_argument(
            '-u', dest='prom_endpoint', help='Prometheus URL (user:pass from env PROMCRED)')
        PARSER.add_argument(
            '--show-sources', default=False, action='store_true', dest='show_sources', help='Shows which metrics contributed for each record')
        PARSER.add_argument(
            '--hide-ignored', default=False, action='store_true', dest='hide_ignored', help='Omits records marked as "ignored" (removed from final resultset)')
        PARSER.add_argument(
            '--filter', default='', dest='filter', help='Filters out resultset for anything that doesn\'t match the field=value combinations, use comma for several')
        PARSER.add_argument(
            '--exclude', default='', dest='exclude', help='Filters out resultset for anything that matches the field=value combinations (opposite of --filter), use comma for several')
        PARSER.add_argument(
            '--only', default='', dest='only', help='Execute only config with specified name')
        PARSER.add_argument(
            '--except', default='', dest='exception', help='Execute all config but specified name (opposite of --only)')
        PARSER.add_argument('--version', action='version', version='%(prog)s {}'.format(VERSION))
        return PARSER.parse_args()


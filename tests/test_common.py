

import os

class MockOptions(object):
    pass

class TestContext():

    def __init__(self):
        pass

    def get_options(self):
        options = MockOptions()
        options.config = './tests/configmap-prom-inventory-test.yaml'
        options.debug = 2
        options.prom_endpoint = 'https://your-prometheus-1.net'
        options.show_sources = True
        options.hide_ignored = True
        options.filter = ''
        options.exclude = ''
        options.only = ''
        options.exception = 'disk:smartmon'
        return options

class TestContextOnline(TestContext):
    def __init__(self):
        super().__init__()
        self.mode = 'online'

class TestContextOffline(TestContext):
    def __init__(self):
        super().__init__()
        self.mode = 'offline'

    def get_options(self):
        options = MockOptions()
        options.config = './tests/configmap-prom-inventory-test.yaml'
        options.debug = 3
        options.prom_endpoint = 'https://your-prometheus-1.net'
        options.show_sources = True
        options.hide_ignored = True
        options.filter = ''
        options.exclude = ''
        options.only = ''
        options.exception = 'disk:smartmon'
        return options

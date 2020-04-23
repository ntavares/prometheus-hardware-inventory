Developing Tests
================
When developing tests, be aware that the fixtures_* are meant to be executed both from:
* test_online.py - against a live API. BE CAREFUL with the names, namespaces and the scope of your actions;
* test_offline.py - using the built-in Dumper (for both reads and writes)

To run non-destructive tests only, run with (either online or offline):
```
nosetests -v -a '!destructive'
```

You can also use the Attrib to choose online or offline only:
```
nosetests -v -a '!destructive,online'
```

Other attribs used:
- input (loading the data)

You can verify the test coverage with:
```
nosetests -v --with-coverage --cover-package=PrometheusInventory tests/test_offline.py  2>&1  # untested?
```

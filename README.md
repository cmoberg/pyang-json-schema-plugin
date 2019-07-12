# pyang-json-schema-plugin

This is a pyang JSON Schema output plugin. It takes YANG files and tries to produce a JSON Schema that validates JSON content payload as defined in [RFC7951](https://tools.ietf.org/html/rfc7951).

Here's an example when running from the `test` directory:
```
$ cd test/
$ pyang --plugindir ../ -f json-schema ./test-module.yang > test-module.jsonschema
```

You can then validate the generated schema using e.g. the [tv4](https://github.com/geraintluff/tv4) tool like so:
```
$ tv4 -b -v -s test-module.jsonschema -j test-module.json
Schema is valid
JSON is valid.
```


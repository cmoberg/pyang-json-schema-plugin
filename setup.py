import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='pyang-json-schema-plugin',
    version='0.1',
    description=('A pyang plugin to produce a JSON Schema that validates JSON content payload'),
    long_description=read('README.md'),
    packages=['jsonschema'],
    author='Carl Moberg',
    author_email='camoberg@cisco.com',
    license='New-style BSD',
    url='https://github.com/cmoberg/pyang-jsontree-plugin',
    install_requires=['pyang'],
    include_package_data=True,
    keywords=['yang', 'extraction', 'jsonschema'],
    classifiers=[],
    entry_points={'pyang.plugin': 'json_tree_plugin=jsonschema.jsonschema:pyang_plugin_init'}
)
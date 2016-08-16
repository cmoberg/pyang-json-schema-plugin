"""JSON Schema generator
"""
from __future__ import print_function

import optparse
import sys
import re
import string
import logging

import types
import StringIO

import json

from pyang import plugin
from pyang import statements
from pyang import util

debug = False

def pyang_plugin_init():
	plugin.register_plugin(JSONSchemaPlugin())

class JSONSchemaPlugin(plugin.PyangPlugin):

	def add_output_format(self, fmts):
		fmts['json-schema'] = self

	def add_opts(self, optparser):
		optlist = [
			optparse.make_option('--json-schema-debug',
								 dest = 'schema_debug',
								 action = "store_true",
								 help = 'JSON Schema debug'),
			# optparse.make_option('--json-schema-path',
			#                      dest = 'schema_path',
			#                      help = 'JSON Schema path'),
			]

		g = optparser.add_option_group("JSON Schema-specific options")
		g.add_options(optlist)

	def setup_ctx(self, ctx):
		ctx.opts.stmts = None

	def setup_fmt(self, ctx):
		ctx.implicit_errors = False

	def emit(self, ctx, modules, fd):
		if ctx.opts.schema_debug == True:
			logging.basicConfig(level=logging.DEBUG)

		# if ctx.opts.schema_path is not None:
		# 	logging.debug("schema_path: %s", ctx.opts.schema_path)
		# 	path = ctx.opts.schema_path
		# else:
		# 	path = None
		path = None

		res = produce_module(modules[0], path)
		print(json.dumps(res, indent=2))

def find_path(module, path):
	logging.debug("in find_path with: %s %s", module.keyword, module.arg)

	if path is not None:
		p = path.split("/")
		if p[0] == '':
			p = p[1:]

	chs = [ch for ch in module.i_children]
	logging.debug("Path now %s", path)
	if len(path) > 0:
		chs = [ch for ch in chs if ch.arg == path[0]]
		path = path[1:]

def produce_module(module, path):
	logging.debug("in produce_module: %s %s with path %s", module.keyword, module.arg, path)
	res = { "title": module.arg, "$schema": "http://json-schema.org/schema#", "type": "object", "properties": {} }

	# stmt = find_path(module, path)

	for child in module.i_children:
		if child.keyword in statements.data_definition_keywords:
			if child.keyword in producers:
				logging.debug("keyword hit on: %s %s",  child.keyword, child.arg)
				add = producers[child.keyword](child)
				# logging.debug("Add: %s", json.dumps(add, indent=2))
				res["properties"].update(add)
				# logging.debug("Res is now: %s", json.dumps(res, indent=2))
			else:
				logging.debug("keyword miss on: %s %s", child.keyword, child.arg)
		else:
			logging.debug("keyword not in data_definition_keywords: %s %s", child.keyword, child.arg)

	return res


def produce_leaf(stmt):
	dtype = "string"
	arg = qualify_name(stmt)

	rtype = stmt.search_one('type').arg
	if rtype in _numeric_type_trans_tbl:
		dtype, format = numeric_type_trans(rtype)
		res = { arg: { "type": dtype } }
	elif rtype in _other_type_trans_tbl:
		substmts = other_type_trans(rtype, stmt)
		logging.debug("in produce_leaf (from other_type_trans): %s %s %s", stmt.keyword, stmt.arg, substmts)
		res = substmts
	elif rtype == "string":
		res = { arg: { "type": dtype } }
	else:
		logging.debug("MISSING TYPE MAPPING in produce_leaf: %s %s", stmt.keyword, stmt.arg)
		res = { arg: { "type": dtype } }

	return res

def produce_list(stmt):
	logging.debug("in produce_list: %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)

	if stmt.parent.keyword != "list":
		res = { arg: { "type": "array", "items": [] } }
	else:
		res = { "type": "object", "properties": { arg: { "type": "array", "items": [] } } }

	if hasattr(stmt, 'i_children'):
		for s in stmt.i_children:
			if s.keyword in producers:
				logging.debug("keyword hit on: %s %s", s.keyword, s.arg)
				if stmt.parent.keyword != "list":
					res[arg]["items"].append(producers[s.keyword](s))
				else:
					res["properties"][arg]["items"].append(producers[s.keyword](s))					
			else:
				logging.debug("keyword miss on: %s %s", s.keyword, s.arg)
	logging.debug("In produce_list for %s, returning %s", stmt.arg, res)
	return res

def produce_leaf_list(stmt):
	logging.debug("in produce_leaf_list: %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)

	dtype = stmt.search_one('type').arg
	res = { arg: { "type": "array", "items": [ { "type": numeric_type_trans(dtype)[0] } ] } } 
	return res

def produce_container(stmt):
	logging.debug("in produce_container: %s %s %s", stmt.keyword, stmt.arg, stmt.i_module.arg)
	arg = qualify_name(stmt)

	if stmt.parent.keyword != "list":
		res = { arg: { "type": "object", "properties": {} } }
	else:
		res = { "type": "object", "properties": { arg: { "type": "object", "properties": {} } } }

	if hasattr(stmt, 'i_children'):
		for s in stmt.i_children:
			if s.keyword in producers:
				logging.debug("keyword hit on: %s %s", s.keyword, s.arg)
				if stmt.parent.keyword != "list":
					res[arg]["properties"].update(producers[s.keyword](s))
				else:
					res["properties"][arg]["properties"].update(producers[s.keyword](s))
			else:
				logging.debug("keyword miss on: %s %s", s.keyword, s.arg)
	logging.debug("In produce_container, returning %s", res)
	return res

def produce_leafref(stmt):
	# Consider using dereferencing instead?
	logging.debug("in produce_leafref: %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)
	res = {}
	return res

def produce_choice(stmt):
	logging.debug("in produce_choice: %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)

	# https://tools.ietf.org/html/rfc6020#section-7.9.2
	res = { arg: { "oneOf": [] } }

	idx = 0
	for case in stmt.search("case"):
		res[arg]["oneOf"].append(dict())
		if hasattr(case, 'i_children'):
			for ch in case.i_children:
				if ch.keyword in producers:
					logging.debug("keyword hit on (long version): %s %s", ch.keyword, ch.arg)
					res[arg]["oneOf"][idx].update(producers[ch.keyword](ch))
				else:
					logging.debug("keyword miss on: %s %s", ch.keyword, ch.arg)
		idx += 1

	# Short ("case-less") version
	#  https://tools.ietf.org/html/rfc6020#section-7.9.2
	for ch in stmt.substmts:
		logging.debug("checking on keywords with: %s %s", ch.keyword, ch.arg)
		if ch.keyword in [ "container", "leaf", "list", "leaf-list" ]:
			res[arg]["oneOf"].append(dict())
			logging.debug("keyword hit on (short version): %s %s", ch.keyword, ch.arg)
			res[arg]["oneOf"][idx].update(producers[ch.keyword](ch))
		idx += 1
	return res

producers = {
	"module":		produce_module,
	"container": 	produce_container,
	"list": 		produce_list,
	"leaf-list": 	produce_leaf_list,
	"leaf": 		produce_leaf,
	"leafref": 		produce_leafref,
	"choice":		produce_choice,
}

_numeric_type_trans_tbl = {
	# https://tools.ietf.org/html/draft-ietf-netmod-yang-json-02#section-6
	#	YANG      JSON Schema  Extra Format
		"int8":   ("number",   None),
		"int16":  ("number",   None),
		"int32":  ("number",   "int32"),
		"int64":  ("integer",  "int64"),
		"uint8":  ("number",   None),
		"uint16": ("number",   None),
		"uint32": ("integer",  "uint32"),
		"uint64": ("integer",  "uint64"),		
	}

def enumeration_trans(stmt):
	logging.debug("in enumeration_trans with stmt %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)

	enumeration = stmt.search_one("type", "enumeration")
	res = { arg: { "properties": { "type": { "enum": [] } } } }
	for enum in enumeration.search("enum"):
		res[arg]["properties"]["type"]["enum"].append(enum.arg)
	logging.debug("In enumeration_trans for %s, returning %s", arg, res)
	return res

def bits_trans(stmt):
	logging.debug("in bits_trans with stmt %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)
	res = { arg: { "type": "string" } }
	return res

def boolean_trans(stmt):
	logging.debug("in boolean_trans with stmt %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)
	res = { arg: { "type": "boolean" } }
	return res

def empty_trans(stmt):
	logging.debug("in empty_trans with stmt %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)
	res = { arg: { "type": "array", "items": [ { "type": "null" } ] } }
	# Likely needs more/other work per:
	#  https://tools.ietf.org/html/draft-ietf-netmod-yang-json-10#section-6.9
	return res

def union_trans(stmt):
	logging.debug("in union_trans with stmt %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)
	union = stmt.search_one("type", "union")
	res = { arg: { "oneOf": [] } }
	for member in union.search("type"):
		res[arg]["oneOf"].append({"type": numeric_type_trans(member.arg)[0]})
	return res

def instance_identifier_trans(stmt):
	logging.debug("in instance_identifier_trans with stmt %s %s", stmt.keyword, stmt.arg)
	arg = qualify_name(stmt)
	res = { arg: { "type": "string" } }
	return res


_other_type_trans_tbl = {
	# https://tools.ietf.org/html/draft-ietf-netmod-yang-json-02#section-6
	"enumeration": 				enumeration_trans,
	"bits":						bits_trans,
	"boolean":					boolean_trans,
	"empty":					empty_trans,
	"union":					union_trans,
	"instance-identifier":		instance_identifier_trans
}

def numeric_type_trans(dtype):
	ttype = "string"
	tformat = None
	if dtype in _numeric_type_trans_tbl:
		ttype = _numeric_type_trans_tbl[dtype][0]
		tformat = _numeric_type_trans_tbl[dtype][1]

	return ttype, tformat

def other_type_trans(dtype, stmt):
	return _other_type_trans_tbl[dtype](stmt)

def qualify_name(stmt):
   # A namespace-qualified member name MUST be used for all members of a
   # top-level JSON object, and then also whenever the namespaces of the
   # data node and its parent node are different.  In all other cases, the
   # simple form of the member name MUST be used.
	if stmt.parent.parent == None: # We're on top
		pfx = stmt.i_module.arg
		logging.debug("in qualify_name with: %s %s ON TOP", stmt.keyword, stmt.arg)
		return pfx + ":" + stmt.arg
	if stmt.top.arg != stmt.parent.top.arg: # Parent node is different
		pfx = stmt.top.arg
		logging.debug("in qualify_name with: %s %s PARENT DIFFERENT", stmt.keyword, stmt.arg)
		return pfx + ":" + stmt.arg

	# logging.debug("in qualify_name with: %s %s:%s NO PREFIX! %s %s:%s", 
	# 	stmt.keyword, stmt.arg, stmt.top.arg, stmt.parent.keyword, stmt.parent.arg, stmt.parent.top.arg)
	return stmt.arg


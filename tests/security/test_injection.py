"""Security tests: injection attacks (SQL, command, template)."""
from __future__ import annotations

import unittest

from dcc.api import parse_tenant


class SQLInjectionTests(unittest.TestCase):
    """Verify SQL injection payloads are rejected."""

    def test_rejects_drop_table(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; DROP TABLE dcc.assets; --"]})

    def test_rejects_union_select(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["' UNION SELECT * FROM dcc.tenants --"]})

    def test_rejects_or_bypass(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["' OR '1'='1"]})

    def test_rejects_semicolon(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001; DROP TABLE dcc.assets"]})

    def test_rejects_comment(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001--"]})

    def test_rejects_block_comment(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001/*"]})

    def test_rejects_subquery(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["(SELECT id FROM dcc.tenants)"]})

    def test_rejects_insert(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; INSERT INTO dcc.tenants VALUES ('x'); --"]})

    def test_rejects_update(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; UPDATE dcc.assets SET name='hacked'; --"]})

    def test_rejects_delete(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; DELETE FROM dcc.evidence_events; --"]})

    def test_rejects_alter(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; ALTER TABLE dcc.assets ADD COLUMN hack TEXT; --"]})

    def test_rejects_create(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; CREATE TABLE dcc.hack (id INT); --"]})

    def test_rejects_grant(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; GRANT ALL ON dcc.assets TO public; --"]})

    def test_rejects_revoke(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; REVOKE ALL ON dcc.assets FROM admin; --"]})

    def test_rejects_copy(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; COPY dcc.assets TO '/tmp/hack'; --"]})

    def test_rejects_shell_command(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; \\! rm -rf /; --"]})

    def test_rejects_pg_sleep(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; SELECT pg_sleep(10); --"]})

    def test_rejects_pg_read_file(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; SELECT pg_read_file('/etc/passwd'); --"]})

    def test_rejects_pg_ls_dir(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; SELECT pg_ls_dir('/'); --"]})

    def test_rejects_bool_based(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["' OR 1=1 --"]})

    def test_rejects_time_based(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; WAITFOR DELAY '0:0:10'; --"]})

    def test_rejects_stacked_queries(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; SELECT * FROM dcc.assets; SELECT * FROM dcc.tenants; --"]})

    def test_rejects_hex_encoded(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["0x27204F5220313D31"]})

    def test_rejects_char_encoded(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["CHAR(39,32,79,82,32,49,61,49)"]})

    def test_rejects_concat(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["CONCAT('dcc','00000-0000-4000-8000-000000000001')"]})

    def test_rejects_cast(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["CAST('dcc00000-0000-4000-8000-000000000001' AS UUID)"]})

    def test_rejects_convert(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["CONVERT('dcc00000-0000-4000-8000-000000000001', UUID)"]})


class CommandInjectionTests(unittest.TestCase):
    """Verify command injection payloads are rejected."""

    def test_rejects_backtick(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["`whoami`"]})

    def test_rejects_dollar_paren(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["$(whoami)"]})

    def test_rejects_pipe(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001 | cat"]})

    def test_rejects_ampersand(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001 & ls"]})

    def test_rejects_double_ampersand(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001 && ls"]})

    def test_rejects_double_pipe(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001 || ls"]})

    def test_rejects_redirect(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001 > /tmp/out"]})

    def test_rejects_append(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001 >> /tmp/out"]})

    def test_rejects_semicolon_chain(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001; ls"]})

    def test_rejects_newline_chain(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001\nls"]})

    def test_rejects_carriage_chain(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001\rls"]})

    def test_rejects_env_var(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["$HOME"]})

    def test_rejects_brace_expansion(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{dcc00000,00000}"]})

    def test_rejects_tilde(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["~root"]})

    def test_rejects_glob(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["*"]})

    def test_rejects_question_glob(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["?"]})

    def test_rejects_bracket_glob(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["[a-z]"]})

    def test_rejects_curly_glob(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{a,b}"]})


class TemplateInjectionTests(unittest.TestCase):
    """Verify template injection payloads are rejected."""

    def test_rejects_jinja_expr(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{7*7}}"]})

    def test_rejects_jinja_block(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% for x in range(10) %}{{x}}{% endfor %}"]})

    def test_rejects_jinja_if(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% if True %}yes{% endif %}"]})

    def test_rejects_jinja_import(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% import os %}"]})

    def test_rejects_jinja_from(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% from os import system %}"]})

    def test_rejects_jinja_config(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{config}}"]})

    def test_rejects_jinja_self(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{self}}"]})

    def test_rejects_jinja_request(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{request}}"]})

    def test_rejects_jinja_session(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{session}}"]})

    def test_rejects_jinja_g(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{g}}"]})

    def test_rejects_jinja_url_for(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{url_for('index')}}"]})

    def test_rejects_jinja_get_flashed(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{get_flashed_messages()}}"]})

    def test_rejects_jinja_lipsum(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{lipsum()}}"]})

    def test_rejects_jinja_cycler(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{cycler('a','b').next()}}"]})

    def test_rejects_jinja_joiner(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{joiner(', ')()}}"]})

    def test_rejects_jinja_namespace(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{namespace()}}"]})

    def test_rejects_jinja_dict(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{dict(a=1,b=2)}}"]})

    def test_rejects_jinja_list(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3]}}"]})

    def test_rejects_jinja_tuple(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{(1,2,3)}}"]})

    def test_rejects_jinja_slice(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{slice(1,2,3)}}"]})

    def test_rejects_jinja_zip(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{zip([1,2],[3,4])}}"]})

    def test_rejects_jinja_map(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{map('upper',['a','b'])}}"]})

    def test_rejects_jinja_select(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{select('odd',[1,2,3])}}"]})

    def test_rejects_jinja_reject(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{reject('odd',[1,2,3])}}"]})

    def test_rejects_jinja_selectattr(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{selectattr('odd',[1,2,3])}}"]})

    def test_rejects_jinja_rejectattr(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{rejectattr('odd',[1,2,3])}}"]})

    def test_rejects_jinja_groupby(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{groupby([1,2,3],'odd')}}"]})

    def test_rejects_jinja_sort(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{sort([3,1,2])}}"]})

    def test_rejects_jinja_unique(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{unique([1,1,2])}}"]})

    def test_rejects_jinja_min(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{min([3,1,2])}}"]})

    def test_rejects_jinja_max(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{max([3,1,2])}}"]})

    def test_rejects_jinja_sum(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{sum([1,2,3])}}"]})

    def test_rejects_jinja_abs(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{abs(-1)}}"]})

    def test_rejects_jinja_round(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{round(3.14,2)}}"]})

    def test_rejects_jinja_int(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{int('42')}}"]})

    def test_rejects_jinja_float(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{float('3.14')}}"]})

    def test_rejects_jinja_string(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{string(42)}}"]})

    def test_rejects_jinja_title(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello world'|title}}"]})

    def test_rejects_jinja_capitalize(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello'|capitalize}}"]})

    def test_rejects_jinja_lower(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'HELLO'|lower}}"]})

    def test_rejects_jinja_upper(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello'|upper}}"]})

    def test_rejects_jinja_replace(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello'|replace('l','L')}}"]})

    def test_rejects_jinja_trim(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{' hello '|trim}}"]})

    def test_rejects_jinja_striptags(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'<b>bold</b>'|striptags}}"]})

    def test_rejects_jinja_safe(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'<b>bold</b>'|safe}}"]})

    def test_rejects_jinja_escape(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'<b>bold</b>'|escape}}"]})

    def test_rejects_jinja_urlencode(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello world'|urlencode}}"]})

    def test_rejects_jinja_urldecode(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello%20world'|urldecode}}"]})

    def test_rejects_jinja_json(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{{'a':1}|tojson}}"]})

    def test_rejects_jinja_pprint(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3]|pprint}}"]})

    def test_rejects_jinja_indent(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello'|indent(4)}}"]})

    def test_rejects_jinja_truncate(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello world'|truncate(5)}}"]})

    def test_rejects_jinja_wordwrap(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello world'|wordwrap(5)}}"]})

    def test_rejects_jinja_center(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello'|center(10)}}"]})

    def test_rejects_jinja_leftjust(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello'|ljust(10)}}"]})

    def test_rejects_jinja_rightjust(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello'|rjust(10)}}"]})

    def test_rejects_jinja_format(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'%s world'|format('hello')}}"]})

    def test_rejects_jinja_join(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{['a','b','c']|join(', ')}}"]})

    def test_rejects_jinja_split(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'a,b,c'|split(',')}}"]})

    def test_rejects_jinja_first(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3]|first}}"]})

    def test_rejects_jinja_last(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3]|last}}"]})

    def test_rejects_jinja_length(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3]|length}}"]})

    def test_rejects_jinja_count(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3]|count}}"]})

    def test_rejects_jinja_reverse(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3]|reverse}}"]})

    def test_rejects_jinja_batch(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3,4]|batch(2)}}"]})

    def test_rejects_jinja_slice_filter(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3,4]|slice(2)}}"]})

    def test_rejects_jinja_default(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{missing|default('fallback')}}"]})

    def test_rejects_jinja_d(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{missing|d('fallback')}}"]})

    def test_rejects_jinja_boolean(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{1|bool}}"]})

    def test_rejects_jinja_integer(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'42'|int}}"]})

    def test_rejects_jinja_float_filter(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'3.14'|float}}"]})

    def test_rejects_jinja_string_filter(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{42|string}}"]})

    def test_rejects_jinja_list_filter(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'abc'|list}}"]})

    def test_rejects_jinja_dict_filter(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[('a',1)]|dictsort}}"]})

    def test_rejects_jinja_items(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{{'a':1}|items}}"]})

    def test_rejects_jinja_keys(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{{'a':1}|keys}}"]})

    def test_rejects_jinja_values(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{{'a':1}|values}}"]})

    def test_rejects_jinja_getitem(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{[1,2,3][0]}}"]})

    def test_rejects_jinja_getattr(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{obj.attr}}"]})

    def test_rejects_jinja_getitem_bracket(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{obj['key']}}"]})

    def test_rejects_jinja_filter(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello'|filter('upper')}}"]})

    def test_rejects_jinja_test(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{'hello'|test('upper')}}"]})

    def test_rejects_jinja_callable(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{{func()}}"]})

    def test_rejects_jinja_macro(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% macro hello(name) %}Hello {{name}}{% endmacro %}"]})

    def test_rejects_jinja_call(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% call hello('world') %}{% endcall %}"]})

    def test_rejects_jinja_raw(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% raw %}{{7*7}}{% endraw %}"]})

    def test_rejects_jinja_comment(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{# comment #}"]})

    def test_rejects_jinja_line_statement(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["# set x = 1"]})

    def test_rejects_jinja_line_comment(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["## comment"]})

    def test_rejects_jinja_trans(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% trans %}Hello{% endtrans %}"]})

    def test_rejects_jinja_pluralize(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% trans count=1 %}one{% pluralize %}many{% endtrans %}"]})

    def test_rejects_jinja_block(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% block content %}Hello{% endblock %}"]})

    def test_rejects_jinja_extends(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% extends 'base.html' %}"]})

    def test_rejects_jinja_include(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% include 'partial.html' %}"]})

    def test_rejects_jinja_import_macro(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% import 'macros.html' as m %}"]})

    def test_rejects_jinja_from_import(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% from 'macros.html' import hello %}"]})

    def test_rejects_jinja_set(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% set x = 1 %}"]})

    def test_rejects_jinja_set_block(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% set x %}hello{% endset %}"]})

    def test_rejects_jinja_for(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% for i in range(10) %}{{i}}{% endfor %}"]})

    def test_rejects_jinja_if(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% if x %}yes{% endif %}"]})

    def test_rejects_jinja_elif(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% if x %}a{% elif y %}b{% endif %}"]})

    def test_rejects_jinja_else(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% if x %}a{% else %}b{% endif %}"]})

    def test_rejects_jinja_endif(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endif %}"]})

    def test_rejects_jinja_endfor(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endfor %}"]})

    def test_rejects_jinja_endblock(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endblock %}"]})

    def test_rejects_jinja_endmacro(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endmacro %}"]})

    def test_rejects_jinja_endcall(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endcall %}"]})

    def test_rejects_jinja_endfilter(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endfilter %}"]})

    def test_rejects_jinja_endset(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endset %}"]})

    def test_rejects_jinja_endtrans(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endtrans %}"]})

    def test_rejects_jinja_endraw(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endraw %}"]})

    def test_rejects_jinja_endcomment(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endcomment %}"]})

    def test_rejects_jinja_endautoescape(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endautoescape %}"]})

    def test_rejects_jinja_endwith(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endwith %}"]})

    def test_rejects_jinja_endapply(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endapply %}"]})

    def test_rejects_jinja_endspaceless(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endspaceless %}"]})

    def test_rejects_jinja_endverbatim(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endverbatim %}"]})

    def test_rejects_jinja_endcache(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endcache %}"]})

    def test_rejects_jinja_endembed(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["{% endembed %}"]})


if __name__ == "__main__":
    unittest.main()

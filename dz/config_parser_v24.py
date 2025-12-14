#!/usr/bin/env python3

import sys
import argparse
from lark import Lark, Transformer, v_args, UnexpectedInput, Tree
from lark.exceptions import VisitError
import xml.etree.ElementTree as ET
import xml.dom.minidom


grammar = r"""
    ?start: (assignment | value)*

    assignment: "def" NAME "=" value -> assign_const

    const_expr: QUESTION_MARK LBRACKET NAME RBRACKET -> resolve_const

    ?value: number
          | string
          | array
          | const_expr

    array: "{" value ("," value)* "}"

    number: NUMBER -> number
    string: STRING_DOUBLE -> string
    NAME: /[_A-Z][_a-zA-Z0-9]*/

    NUMBER: /[+-]?\d+/
    STRING_DOUBLE: /"[^"]*"/
    QUESTION_MARK: "?"
    LBRACKET: "["
    RBRACKET: "]"

    COMMENT_SINGLE: /--.*/
    COMMENT_MULTI: /\|#[\s\S]*?#\|/

    %import common.WS
    %ignore WS
    %ignore COMMENT_SINGLE
    %ignore COMMENT_MULTI
"""


@v_args(inline=True)
class ConfigTransformer(Transformer):
    def __init__(self):
        self.constants = {}
        self.assignments = {}
        super().__init__()

    def start(self, *items):
        result_dict = {}
        unnamed_counter = 0

        for item in items:
            if isinstance(item, tuple) and len(item) == 2:
                name, val = item
                result_dict[name] = val
            elif isinstance(item, Tree) and item.data == 'assign_const':
                continue
            else:
                key = f"item_{unnamed_counter}"
                result_dict[key] = item
                unnamed_counter += 1

        return result_dict

    def assign_const(self, name_token, value):
        name = name_token.value
        self.constants[name] = value
        self.assignments[name] = value
        return name, value

    def resolve_const(self, question_mark, lbracket, name_token, rbracket):
        name = name_token.value
        if name not in self.constants:
            raise VisitError(f"Undefined constant '{name}' used in expression ?[{name}]")
        return self.constants[name]

    def number(self, token):
        return int(token)

    def string(self, token):
        return token[1:-1]

    def array(self, *items):
        return list(items)


def generate_xml_from_dict(data, root_name="config"):
    def _to_xml_recurse(parent_element, data):
        if isinstance(data, dict):
            for key, value in data.items():
                child_elem = ET.SubElement(parent_element, key)
                _to_xml_recurse(child_elem, value)
        elif isinstance(data, list):
            array_container = ET.SubElement(parent_element, "array")
            for item in data:
                item_elem = ET.SubElement(array_container, "item")
                _to_xml_recurse(item_elem, item)
        else:
            parent_element.text = str(data)

    root = ET.Element(root_name)
    _to_xml_recurse(root, data)

    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = xml.dom.minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding=None)
    lines = pretty_xml.splitlines(True)
    if lines and lines[0].startswith("<?xml"):
        return ''.join(lines[1:]).strip()
    else:
        return pretty_xml.strip()


def main():
    parser = argparse.ArgumentParser(
        description='Parse custom config language file (Variant 24) and convert to XML.'
    )
    parser.add_argument('input_file', type=str, help='Path to the input configuration file')
    args = parser.parse_args()

    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        parser_instance = Lark(grammar, parser='lalr')
        parse_tree = parser_instance.parse(text)
        transformer = ConfigTransformer()
        result_dict = transformer.transform(parse_tree)
        xml_output = generate_xml_from_dict(result_dict)
        print(xml_output)

    except UnexpectedInput as e:
        print(f"Syntax error in the configuration file: {e}", file=sys.stderr)
        sys.exit(1)
    except VisitError as e:
        print(f"Runtime error during processing: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path
from typing import Any, Optional, Tuple
import re

import yaml
import click

from . import __version__
from .Harness import Harness
from .wv_helper import expand, open_file_read

COMMON_LIB = (Path(__file__).parent / 'common' / 'lib.yaml').resolve()


def parse(yaml_input: str,
          file_out: (str, Path) = None,
          return_types: (None, str, Tuple[str]) = None) -> Any:
    """
    Parses yaml input string and does the high-level harness conversion

    :param yaml_input: a string containing the yaml input data
    :param file_out:
    :param return_types: if None, then returns None; if the value is a string,
        then a corresponding data format will be returned; if the value is a
        tuple of strings, then for every valid format in the `return_types`
        tuple, another return type will be generated and returned in the same
        order; currently supports:
            - "png" - will return the PNG data
            - "svg" - will return the SVG data
            - "harness" - will return the `Harness` instance
    """

    yaml_data = yaml.safe_load(yaml_input)

    harness = Harness()

    # add items
    sections = ['connectors', 'cables', 'connections']
    types = [dict, dict, list]
    for sec, ty in zip(sections, types):
        if sec in yaml_data and type(yaml_data[sec]) == ty:
            if len(yaml_data[sec]) > 0:
                if ty == dict:
                    for key, attribs in yaml_data[sec].items():
                        # The Image dataclass might need to open an image file
                        # with a relative path.
                        image = attribs.get('image')
                        if isinstance(image, dict):
                            image['gv_dir'] = Path(file_out if file_out
                                                   else '').parent

                        if sec == 'connectors':
                            if not attribs.get('autogenerate', False):
                                harness.add_connector(name=key, **attribs)
                        elif sec == 'cables':
                            harness.add_cable(name=key, **attribs)
            else:
                pass  # section exists but is empty
        else:  # section does not exist, create empty section
            if ty == dict:
                yaml_data[sec] = {}
            elif ty == list:
                yaml_data[sec] = []

    # add connections
    def check_designators(what, where):
        for i, x in enumerate(what):
            if x not in yaml_data[where[i]]:
                return False
        return True

    autogenerated_ids = {}
    for connection in yaml_data['connections']:
        # find first component (potentially nested inside list or dict)
        first_item = connection[0]
        if isinstance(first_item, list):
            first_item = first_item[0]
        elif isinstance(first_item, dict):
            first_item = list(first_item.keys())[0]
        elif isinstance(first_item, str):
            pass

        # check which section the first item belongs to
        alternating_sections = ['connectors', 'cables']
        for index, section in enumerate(alternating_sections):
            if first_item in yaml_data[section]:
                expected_index = index
                break
        else:
            raise Exception('First item not found anywhere.')
        # flip once since it is flipped back at the *beginning* of every loop
        expected_index = 1 - expected_index

        # check that all iterable items (lists and dicts) are the same length
        # and that they are alternating between connectors and cables/bundles,
        # starting with either
        itemcount = None
        for item in connection:
            # make sure items alternate between connectors and cables
            expected_index = 1 - expected_index
            expected_section = alternating_sections[expected_index]
            if isinstance(item, list):
                itemcount_new = len(item)
                for subitem in item:
                    if subitem not in yaml_data[expected_section]:
                        raise Exception(f'{subitem} is not in '
                                        f'{expected_section}')
            elif isinstance(item, dict):
                if len(item.keys()) != 1:
                    raise Exception('Dicts may contain only one key here!')
                itemcount_new = len(expand(list(item.values())[0]))
                subitem = list(item.keys())[0]
                if subitem not in yaml_data[expected_section]:
                    raise Exception(f'{subitem} is not in {expected_section}')
            elif isinstance(item, str):
                if item not in yaml_data[expected_section]:
                    raise Exception(f'{item} is not in {expected_section}')
                continue
            if itemcount is not None and itemcount_new != itemcount:
                raise Exception('All lists and dict lists must '
                                'be the same length!')
            itemcount = itemcount_new
        if itemcount is None:
            raise Exception('No item revealed the number '
                            'of connections to make!')

        # populate connection list
        connection_list = []
        for i, item in enumerate(connection):
            if isinstance(item, str):  # one single-pin component was specified
                sublist = []
                for i in range(1, itemcount + 1):
                    if yaml_data['connectors'][item].get('autogenerate'):
                        autogenerated_ids[item] = 1 + \
                            autogenerated_ids.get(item, 0)
                        new_id = f'_{item}_{autogenerated_ids[item]}'
                        harness.add_connector(new_id,
                                              **yaml_data['connectors'][item])
                        sublist.append([new_id, 1])
                    else:
                        sublist.append([item, 1])
                connection_list.append(sublist)
            # a list of single-pin components were specified
            elif isinstance(item, list):
                sublist = []
                for subitem in item:
                    if yaml_data['connectors'][subitem].get('autogenerate'):
                        autogenerated_ids[subitem] = 1 + \
                            autogenerated_ids.get(subitem, 0)
                        new_id = f'_{subitem}_{autogenerated_ids[subitem]}'
                        harness.add_connector(new_id,
                                              **yaml_data['connectors'][subitem])  # noqa
                        sublist.append([new_id, 1])
                    else:
                        sublist.append([subitem, 1])
                connection_list.append(sublist)
            # a component with multiple pins was specified
            elif isinstance(item, dict):
                sublist = []
                id = list(item.keys())[0]
                pins = expand(list(item.values())[0])
                for pin in pins:
                    sublist.append([id, pin])
                connection_list.append(sublist)
            else:
                raise Exception('Unexpected item in connection list')

        # actually connect components using connection list
        for i, item in enumerate(connection_list):
            id = item[0][0]  # TODO: make more elegant/robust/pythonic
            if id in harness.cables:
                for j, con in enumerate(item):
                    # list started with a cable, no connector to join on
                    # left side
                    if i == 0:
                        from_name, from_pin = None, None
                    else:
                        from_name, from_pin = connection_list[i - 1][j][0:2]
                    via_name, via_pin = item[j][0:2]
                    # list ends with a cable, no connector to join on right side
                    if i == len(connection_list) - 1:
                        to_name, to_pin = None, None
                    else:
                        to_name, to_pin = connection_list[i + 1][j][0:2]
                    harness.connect(from_name,
                                    from_pin,
                                    via_name,
                                    via_pin,
                                    to_name,
                                    to_pin)

    if "additional_bom_items" in yaml_data:
        for line in yaml_data["additional_bom_items"]:
            harness.add_bom_item(line)

    if file_out is not None:
        harness.output(filename=file_out, fmt=('png', 'svg'), view=False)

    if return_types is not None:
        returns = []
        # only one return type speficied
        if isinstance(return_types, str):
            return_types = [return_types]

        return_types = [t.lower() for t in return_types]

        for rt in return_types:
            if rt == 'png':
                returns.append(harness.png)
            if rt == 'svg':
                returns.append(harness.svg)
            if rt == 'harness':
                returns.append(harness)

        return tuple(returns) if len(returns) != 1 else returns[0]


def parse_file(yaml_file: str, file_out: (str, Path) = None) -> None:
    with open_file_read(yaml_file) as file:
        yaml_input = file.read()

    if not file_out:
        fn, fext = os.path.splitext(yaml_file)
        file_out = fn
    file_out = os.path.abspath(file_out)

    parse(yaml_input, file_out=file_out)


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.version_option(__version__, prog_name="wireviz")
@click.argument('srcfile',
                type=click.Path(exists=True,
                                file_okay=True,
                                dir_okay=False,
                                writable=False,
                                readable=True,
                                resolve_path=True,
                                allow_dash=False))
@click.option('--prepend-common-lib', '--common', '-c',
              is_flag=True,
              default=False,
              help=("includes the rrc-wireviz common library located in "
                    f"{COMMON_LIB!s}"))
@click.option('--outfile', '-o',
              type=click.Path(exists=False,
                              file_okay=True,
                              dir_okay=False,
                              writable=True,
                              readable=False,
                              resolve_path=True,
                              allow_dash=True),
              help=("output file, extension is ignored; "
                    "defaults to input filename"))
@click.option('--prepend-file', '--prepend', '-i',  # i for include
              type=click.Path(exists=True,
                              file_okay=True,
                              dir_okay=False,
                              writable=False,
                              readable=True,
                              resolve_path=True,
                              allow_dash=False),
              help="file(s) to prepend/include to the srcfile",
              multiple=True)
def main(srcfile: Optional[Path],
         prepend_common_lib: bool,
         outfile: Optional[Path] = None,
         prepend_file: Optional[Tuple[Path, ...]] = None) -> None:
    '''Generate cable and wiring harness documentation from YAML descriptions.

    Documentation can be found on the ISBU Hardware Wiki:
    http://isbuhome/isbuwiki/index.php/Wireviz
    '''
    def convert_to_pathlib(path):
        if isinstance(path, Path):
            return path
        elif isinstance(path, bytes):
            return Path(path.decode())
        elif isinstance(path, str):
            return Path(path)
        else:
            raise TypeError(f"Unexpected path type {type(path)}")

    # Source file is specified
    srcfile = convert_to_pathlib(srcfile)

    if outfile:
        outfile = convert_to_pathlib(outfile)
    if prepend_file:
        prepended_file = ()
        for i, file in enumerate(prepend_file):
            prepended_file += (convert_to_pathlib(file),)
        prepend_file = prepended_file

    with open_file_read(srcfile) as src:
        yaml_input = src.read()

    # Prepend the common library
    prepend = ''
    if prepend_common_lib:
        with open(COMMON_LIB) as src:
            file = src.read()
        # Make all the file paths absolute
        for filepath in re.finditer(r'^\s+src: (.+)$', file, re.MULTILINE):
            path = (COMMON_LIB.parent / filepath.group(1)).resolve()
            file = file.replace(filepath.group(1), str(path))
        prepend += file

    # Prepend other files
    for filename in (prepend_file or []):
        with open(filename) as src:
            file = src.read()
        # Make all the file paths absolute
        for filepath in re.finditer(r'^\s+src: (.+)$', file, re.MULTILINE):
            path = (filename.parent / filepath.group(1)).resolve()
            file = file.replace(filepath.group(1), str(path))
        prepend += file

    yaml_input = prepend + yaml_input

    if outfile:
        outfile.parent.mkdir(parents=True, exist_ok=True)
        file_out = f"{outfile.parents[0] / outfile.stem!s}"
    else:
        file_out = f"{srcfile.parents[0] / srcfile.stem!s}"

    parse(yaml_input, file_out=file_out)

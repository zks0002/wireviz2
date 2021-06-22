#!/usr/bin/env python
# -*- coding: utf-8 -*-
from collections import Counter
from typing import List
from pathlib import Path
import re

from wireviz.DataClasses import (
    Connector,
    Cable)
from graphviz import Graph
from wireviz import (
    wv_colors,
    __version__,
    APP_NAME,
    APP_URL)
from wireviz.wv_colors import get_color_hex
from wireviz.wv_helper import (
    awg_equiv,
    mm2_equiv,
    m2in,
    in2m,
    tuplelist2tsv,
    nested_html_table,
    flatten2d,
    index_if_list,
    html_line_breaks,
    remove_line_breaks,
    open_file_read,
    open_file_write,
    html_colorbar,
    html_image,
    html_caption,
    manufacturer_info_field)


class Harness:

    def __init__(self):
        self.color_mode = 'SHORT'
        self.connectors = {}
        self.cables = {}
        self.additional_bom_items = []
        self.length_unit = 'm'

    def add_connector(self, name: str, *args, **kwargs) -> None:
        self.connectors[name] = Connector(name, *args, **kwargs)

    def add_cable(self, name: str, *args, **kwargs) -> None:
        self.cables[name] = Cable(name, *args, **kwargs)

    def add_bom_item(self, item: dict) -> None:
        if 'length_unit' in item:
            self.length_unit = item['length_unit']
        else:
            self.additional_bom_items.append(item)

    def connect(self,
                from_name: str,
                from_pin: (int, str),
                via_name: str,
                via_pin: (int, str),
                to_name: str,
                to_pin: (int, str)) -> None:
        # check from and to connectors
        for (name, pin) in zip([from_name, to_name], [from_pin, to_pin]):
            if name is not None and name in self.connectors:
                connector = self.connectors[name]
                if pin in connector.pins and pin in connector.pinlabels:
                    if connector.pins.index(pin) == \
                       connector.pinlabels.index(pin):
                        # TODO: Maybe issue a warning? It's not worthy of an
                        # exception if it's unambiguous, but maybe risky?
                        pass
                    else:
                        raise Exception(f'{name}:{pin} is defined both in '
                                        'pinlabels and pins, for different '
                                        'pins.')
                if pin in connector.pinlabels:
                    if connector.pinlabels.count(pin) > 1:
                        raise Exception(f'{name}:{pin} is defined more than '
                                        'once.')
                    else:
                        index = connector.pinlabels.index(pin)
                        # map pin name to pin number
                        pin = connector.pins[index]

                        if name == from_name:
                            from_pin = pin
                        if name == to_name:
                            to_pin = pin
                if pin not in connector.pins:
                    raise Exception(f'{name}:{pin} not found.')

        self.cables[via_name].connect(from_name, from_pin, via_pin,
                                      to_name, to_pin)
        if from_name in self.connectors:
            self.connectors[from_name].activate_pin(from_pin)
        if to_name in self.connectors:
            self.connectors[to_name].activate_pin(to_pin)

    def create_graph(self) -> Graph:
        dot = Graph()
        dot.body.append(f'// Graph generated by {APP_NAME} {__version__}')
        dot.body.append(f'// {APP_URL}')
        font = 'arial'
        dot.attr('graph', rankdir='LR',
                 ranksep='2',
                 bgcolor='white',
                 nodesep='0.33',
                 fontname=font)
        dot.attr('node', shape='record',
                 style='filled',
                 fillcolor='white',
                 fontname=font)
        dot.attr('edge', style='bold',
                 fontname=font)

        # prepare ports on connectors depending on which side they will connect
        for _, cable in self.cables.items():
            for connection_color in cable.connections:
                if connection_color.from_port is not None:  # connect to left
                    self.connectors[connection_color.from_name].ports_right = True  # noqa
                if connection_color.to_port is not None:  # connect to right
                    self.connectors[connection_color.to_name].ports_left = True

        for connector in self.connectors.values():

            html = []

            rows = [[connector.name if connector.show_name else None],
                    [f'P/N: {connector.pn}' if connector.pn else None,
                     html_line_breaks(manufacturer_info_field(connector.manufacturer,  # noqa
                                                              connector.mpn))],
                    [html_line_breaks(connector.type),
                     html_line_breaks(connector.subtype),
                     f'{connector.pincount}-pin' if connector.show_pincount
                        else None,
                     connector.color, html_colorbar(connector.color)],
                    '<!-- connector table -->' if connector.style != 'simple'
                        else None,
                    [html_image(connector.image)],
                    [html_caption(connector.image)],
                    [html_line_breaks(connector.notes)]]
            html.extend(nested_html_table(rows))

            if connector.style != 'simple':
                pinhtml = []
                pinhtml.append('<table border="0" cellspacing="0" '
                               'cellpadding="3" cellborder="1">')

                for pin, pinlabel in zip(connector.pins, connector.pinlabels):
                    if (connector.hide_disconnected_pins and
                            not connector.visible_pins.get(pin, False)):
                        continue
                    pinhtml.append('   <tr>')
                    if connector.ports_left:
                        pinhtml.append(f'    <td port="p{pin}l">{pin}</td>')
                    if pinlabel:
                        pinhtml.append(f'    <td>{pinlabel}</td>')
                    if connector.ports_right:
                        pinhtml.append(f'    <td port="p{pin}r">{pin}</td>')
                    pinhtml.append('   </tr>')

                pinhtml.append('  </table>')

                html = [row.replace('<!-- connector table -->',
                                    '\n'.join(pinhtml)) for row in html]

            html = '\n'.join(html)
            dot.node(connector.name,
                     label=f'<\n{html}\n>',
                     shape='none',
                     margin='0',
                     style='filled',
                     fillcolor='white')

            if len(connector.loops) > 0:
                dot.attr('edge', color='#000000:#ffffff:#000000')
                if connector.ports_left:
                    loop_side = 'l'
                    loop_dir = 'w'
                elif connector.ports_right:
                    loop_side = 'r'
                    loop_dir = 'e'
                else:
                    raise Exception('No side for loops')
                for loop in connector.loops:
                    arg1 = f'{connector.name}:p{loop[0]}{loop_side}:{loop_dir}'
                    arg2 = f'{connector.name}:p{loop[1]}{loop_side}:{loop_dir}'
                    dot.edge(arg1, arg2)

        # determine if there are double- or triple-colored wires in the harness;
        # if so, pad single-color wires to make all wires of equal thickness
        pad = any(len(colorstr) > 2 for cable in self.cables.values()
                  for colorstr in cable.colors)

        for cable in self.cables.values():

            html = []

            awg_fmt = ''
            length_fmt = ''
            if cable.show_equiv:
                # Only convert units we actually know about, i.e. currently
                # mm2 and awg --- other units _are_ technically allowed,
                # and passed through as-is.
                if cable.gauge_unit == 'mm\u00B2':
                    awg_fmt = f' ({awg_equiv(cable.gauge)} AWG)'
                elif cable.gauge_unit.upper() == 'AWG':
                    awg_fmt = f' ({mm2_equiv(cable.gauge)} mm\u00B2)'

                if cable.length_unit == 'in':
                    length_fmt = f' ({in2m(cable.length):.3f} m)'
                elif cable.length_unit == 'm':
                    length_fmt = f' ({m2in(cable.length):.3f} in)'
                else:
                    raise Exception(f'Only m or in length units are supported, '
                                    f'not {cable.length_unit}')

            name = cable.name if cable.show_name else None

            cable_pn = None
            if cable.pn and not isinstance(cable.pn, list):
                cable_pn = f'P/N: {cable.pn}'

            cable_mfg = None
            if not isinstance(cable.manufacturer, list):
                cable_mfg = cable.manufacturer

            cable_mpn = None
            if not isinstance(cable.mpn, list):
                cable_mpn = cable.mpn

            mfg = manufacturer_info_field(cable_mfg, cable_mpn)

            wirecount = f'{cable.wirecount}x' if cable.show_wirecount else None

            gauge = None
            if cable.gauge:
                gauge = f'{cable.gauge} {cable.gauge_unit}{awg_fmt}'

            shield = '+ S' if cable.shield else None

            length = None
            if cable.length > 0:
                length = f'{cable.length} {cable.length_unit}{length_fmt}'

            rows = [[name],
                    [cable_pn,
                     html_line_breaks(mfg)],
                    [html_line_breaks(cable.type),
                     wirecount,
                     gauge,
                     shield,
                     length,
                     cable.color,
                     html_colorbar(cable.color)],
                    '<!-- wire table -->',
                    [html_image(cable.image)],
                    [html_caption(cable.image)],
                    [html_line_breaks(cable.notes)]]
            html.extend(nested_html_table(rows))

            wirehtml = []
            # conductor table
            wirehtml.append('<table border="0" cellspacing="0" cellborder="0">')
            wirehtml.append('   <tr><td>&nbsp;</td></tr>')

            for i, connection_color in enumerate(cable.colors, 1):
                wirehtml.append('   <tr>')
                wirehtml.append(f'    <td><!-- {i}_in --></td>')
                wvcolors = wv_colors.translate_color(connection_color,
                                                     self.color_mode)
                wirehtml.append(f'    <td>{wvcolors}</td>')
                wirehtml.append(f'    <td><!-- {i}_out --></td>')
                wirehtml.append('   </tr>')

                bgcolors = ['#000000']
                bgcolors += get_color_hex(connection_color, pad=pad)
                bgcolors += ['#000000']
                wirehtml.append('   <tr>')
                wirehtml.append('    <td colspan="3" border="0" '
                                f'cellspacing="0" cellpadding="0" port="w{i}" '
                                f'height="{(2 * len(bgcolors))}">')
                wirehtml.append('     <table cellspacing="0" cellborder="0" '
                                'border="0">')
                # Reverse to match the curved wires when more than 2 colors
                for j, bgcolor in enumerate(bgcolors[::-1]):
                    color = bgcolor if bgcolor != "" else \
                        wv_colors.default_color
                    wirehtml.append('      <tr><td colspan="3" cellpadding="0" '
                                    f'height="2" bgcolor="{color}" border="0">'
                                    '</td></tr>')
                wirehtml.append('     </table>')
                wirehtml.append('    </td>')
                wirehtml.append('   </tr>')
                # for bundles individual wires can have part information
                if(cable.category == 'bundle'):
                    # create a list of wire parameters
                    wireidentification = []
                    if isinstance(cable.pn, list):
                        wireidentification.append(f'P/N: {cable.pn[i - 1]}')
                    mfg = None
                    if isinstance(cable.manufacturer, list):
                        mfg = cable.manufacturer[i - 1]
                    mpn = None
                    if isinstance(cable.mpn, list):
                        mpn = cable.mpn[i - 1]
                    mfg_info = manufacturer_info_field(mfg, mpn)
                    if mfg_info:
                        wireidentification.append(html_line_breaks(mfg_info))
                    # print parameters into a table row under the wire
                    if(len(wireidentification) > 0):
                        wirehtml.append('   <tr><td colspan="3">')
                        wirehtml.append('    <table border="0" cellspacing="0" '
                                        'cellborder="0"><tr>')
                        for attrib in wireidentification:
                            wirehtml.append(f'     <td>{attrib}</td>')
                        wirehtml.append('    </tr></table>')
                        wirehtml.append('   </td></tr>')

            if cable.shield:
                wirehtml.append('   <tr><td>&nbsp;</td></tr>')  # spacer
                wirehtml.append('   <tr>')
                wirehtml.append('    <td><!-- s_in --></td>')
                wirehtml.append('    <td>Shield</td>')
                wirehtml.append('    <td><!-- s_out --></td>')
                wirehtml.append('   </tr>')
                if isinstance(cable.shield, str):
                    # shield is shown with specified color and black borders
                    shield_color_hex = wv_colors.get_color_hex(cable.shield)[0]
                    attributes = (f'height="6" bgcolor="{shield_color_hex}" '
                                  f'border="2" sides="tb"')
                else:
                    # shield is shown as a thin black wire
                    attributes = f'height="2" bgcolor="#000000" border="0"'
                wirehtml.append(f'   <tr><td colspan="3" cellpadding="0" '
                                f'{attributes} port="ws"></td></tr>')

            wirehtml.append('   <tr><td>&nbsp;</td></tr>')
            wirehtml.append('  </table>')

            html = [row.replace('<!-- wire table -->',
                                '\n'.join(wirehtml)) for row in html]

            # connections
            for connection_color in cable.connections:
                # check if it's an actual wire and not a shield
                if isinstance(connection_color.via_port, int):
                    colors = ['#000000']
                    colors += wv_colors.get_color_hex(
                        cable.colors[connection_color.via_port - 1], pad=pad)
                    colors += ['#000000']
                    dot.attr('edge', color=':'.join(colors))
                else:  # it's a shield connection
                    # shield is shown with specified color and black borders,
                    # or as a thin black wire otherwise
                    color = '#000000'
                    if isinstance(cable.shield, str):
                        colors = ['#000000', shield_color_hex, '#000000']
                        color = ':'.join(colors)
                    dot.attr('edge', color=color)
                if connection_color.from_port is not None:  # connect to left
                    from_port = ''
                    if self.connectors[connection_color.from_name].style != 'simple':  # noqa
                        from_port = f':p{connection_color.from_port}r'
                    code_left_1 = f'{connection_color.from_name}{from_port}:e'
                    code_left_2 = f'{cable.name}:w{connection_color.via_port}:w'
                    dot.edge(code_left_1, code_left_2)
                    from_string = ''
                    if self.connectors[connection_color.from_name].show_name:
                        from_string = (f'{connection_color.from_name}:'
                                       f'{connection_color.from_port}')
                    repl = f'<!-- {connection_color.via_port}_in -->'
                    html = [row.replace(repl, from_string) for row in html]
                if connection_color.to_port is not None:  # connect to right
                    code_right_1 = (f'{cable.name}:w'
                                    f'{connection_color.via_port}:e')
                    to_port = ''
                    if self.connectors[connection_color.to_name].style != 'simple':  # noqa
                        to_port = f':p{connection_color.to_port}l'
                    code_right_2 = f'{connection_color.to_name}{to_port}:w'
                    dot.edge(code_right_1, code_right_2)
                    to_string = ''
                    if self.connectors[connection_color.to_name].show_name:
                        to_string = (f'{connection_color.to_name}:'
                                     f'{connection_color.to_port}')
                    repl = f'<!-- {connection_color.via_port}_out -->'
                    html = [row.replace(repl, to_string) for row in html]

            html = '\n'.join(html)
            style = 'filled,dashed' if cable.category == 'bundle' else ''
            dot.node(cable.name,
                     label=f'<\n{html}\n>',
                     shape='box',
                     style=style,
                     margin='0',
                     fillcolor='white')

        return dot

    @property
    def png(self):
        from io import BytesIO
        graph = self.create_graph()
        data = BytesIO()
        data.write(graph.pipe(format='png'))
        data.seek(0)
        return data.read()

    @property
    def svg(self):
        from io import BytesIO
        graph = self.create_graph()
        data = BytesIO()
        data.write(graph.pipe(format='svg'))
        data.seek(0)
        return data.read()

    def output(self,
               filename: (str, Path),
               view: bool = False,
               cleanup: bool = True,
               fmt: tuple = ('pdf', )) -> None:
        # graphical output
        graph = self.create_graph()
        for f in fmt:
            graph.format = f
            graph.render(filename=filename, view=view, cleanup=cleanup)
        graph.save(filename=f'{filename}.gv')
        # bom output
        bom_list = self.bom_list()
        with open_file_write(f'{filename}.bom.tsv') as file:
            file.write(tuplelist2tsv(bom_list))
        # HTML output
        with open_file_write(f'{filename}.html') as file:
            file.write('<!DOCTYPE html>\n')
            file.write('<html lang="en"><head>\n')
            file.write(' <meta charset="UTF-8">\n')
            file.write(f' <meta name="generator" '
                       f'content="{APP_NAME} {__version__} - {APP_URL}">\n')
            file.write(f' <title>{APP_NAME} Diagram and BOM</title>\n')
            file.write('</head><body style="font-family:Arial">\n')

            file.write('<h1>Diagram</h1>')
            with open_file_read(f'{filename}.svg') as svg:
                file.write(re.sub(
                    '^<[?]xml [^?>]*[?]>[^<]*<!DOCTYPE [^>]*>',
                    '<!-- XML and DOCTYPE declarations '
                    'from SVG file removed -->',
                    svg.read(1024), 1))
                for svgdata in svg:
                    file.write(svgdata)

            file.write('<h1>Bill of Materials</h1>')
            listy = flatten2d(bom_list)
            file.write('<table style="border:1px solid #000000; '
                       'font-size: 14pt; border-spacing: 0px">')
            file.write('<tr>')
            for item in listy[0]:
                file.write('<th style="text-align:left; '
                           'border:1px solid #000000; padding: 8px">'
                           f'{item}</th>')
            file.write('</tr>')
            for row in listy[1:]:
                file.write('<tr>')
                for i, item in enumerate(row):
                    item_str = item.replace('\u00b2', '&sup2;')
                    align = 'text-align:right; ' if listy[0][i] == 'Qty' else ''
                    file.write(f'<td style="{align}border:1px solid #000000; '
                               f'padding: 4px">{item_str}</td>')
                file.write('</tr>')
            file.write('</table>')

            file.write('</body></html>')

    def bom(self):
        bom = []
        bom_connectors = []
        bom_cables = []
        bom_extra = []

        # connectors
        def connector_group(c):
            return (c.type,
                    c.subtype,
                    c.pincount,
                    c.manufacturer,
                    c.mpn,
                    c.pn)
        for group in Counter([connector_group(v)
                              for v in self.connectors.values()]):
            items = {k: v for k, v in self.connectors.items()
                     if connector_group(v) == group}
            shared = next(iter(items.values()))
            designators = list(items.keys())
            designators.sort()
            conn_type = ''
            if shared.type:
                conn_type = f', {remove_line_breaks(shared.type)}'
            conn_subtype = ''
            if shared.subtype:
                conn_subtype = f', {remove_line_breaks(shared.subtype)}'
            conn_pincount = ''
            if shared.style != 'simple':
                conn_pincount = f', {shared.pincount} pins'
            conn_color = ''
            if shared.color:
                f', {shared.color}'
            name = (f'Connector{conn_type}{conn_subtype}'
                    f'{conn_pincount}{conn_color}')
            item = {'item': name,
                    'qty': len(designators),
                    'unit': '',
                    'designators': designators if shared.show_name else '',
                    'manufacturer': remove_line_breaks(shared.manufacturer),
                    'mpn': remove_line_breaks(shared.mpn),
                    'pn': shared.pn}
            bom_connectors.append(item)
            # https://stackoverflow.com/a/73050
            bom_connectors = sorted(bom_connectors, key=lambda k: k['item'])
        bom.extend(bom_connectors)

        # cables
        # TODO: If category can have other non-empty values than 'bundle',
        # maybe it should be part of item name? The category needs to be
        # included in cable_group to keep the bundles excluded.
        def cable_group(c):
            return (c.category,
                    c.type,
                    c.gauge,
                    c.gauge_unit,
                    c.wirecount,
                    c.shield,
                    c.manufacturer,
                    c.mpn,
                    c.pn)
        for group in Counter([cable_group(v) for v in self.cables.values()
                              if v.category != 'bundle']):
            items = {k: v for k, v in self.cables.items()
                     if cable_group(v) == group}
            shared = next(iter(items.values()))
            designators = list(items.keys())
            designators.sort()

            lnorm = m2in if self.length_unit == 'in' else in2m
            lengths = []
            for i in items.values():
                if i.length_unit != self.length_unit:
                    lengths.append(lnorm(i.length))
                else:
                    lengths.append(i.length)
            total_length = sum(lengths)

            cable_type = ''
            if shared.type:
                cable_type = f', {remove_line_breaks(shared.type)}'

            gauge_name = ' wires'
            if shared.gauge:
                gauge_name = f' x {shared.gauge} {shared.gauge_unit}'

            shield_name = ' shielded' if shared.shield else ''
            name = (f'Cable{cable_type}, {shared.wirecount}'
                    f'{gauge_name}{shield_name}')
            item = {'item': name,
                    'qty': round(total_length, 3),
                    'unit': self.length_unit,
                    'designators': designators,
                    'manufacturer': remove_line_breaks(shared.manufacturer),
                    'mpn': remove_line_breaks(shared.mpn),
                    'pn': shared.pn}
            bom_cables.append(item)
        # bundles (ignores wirecount)
        wirelist = []
        # list all cables again, since bundles are represented as wires
        # internally, with the category='bundle' set
        for bundle in self.cables.values():
            if bundle.category == 'bundle':
                # add each wire from each bundle to the wirelist
                for index, color in enumerate(bundle.colors, 0):
                    mfg = remove_line_breaks(index_if_list(bundle.manufacturer,
                                                           index))
                    mpn = remove_line_breaks(index_if_list(bundle.mpn, index))
                    wirelist.append({'type': bundle.type,
                                     'gauge': bundle.gauge,
                                     'gauge_unit': bundle.gauge_unit,
                                     'length': bundle.length,
                                     'length_unit': bundle.length_unit,
                                     'color': color,
                                     'designator': bundle.name,
                                     'manufacturer': mfg,
                                     'mpn': mpn,
                                     'pn': index_if_list(bundle.pn, index)})

        # join similar wires from all the bundles to a single BOM item
        def wire_group(w):
            return (w.get('type', None),
                    w['gauge'],
                    w['gauge_unit'],
                    w['color'],
                    w['manufacturer'],
                    w['mpn'],
                    w['pn'])
        for group in Counter([wire_group(v) for v in wirelist]):
            items = [v for v in wirelist if wire_group(v) == group]
            shared = items[0]
            designators = [i['designator'] for i in items]
            designators = list(dict.fromkeys(designators))  # remove duplicates
            designators.sort()
            total_length = sum(i['length'] for i in items)
            wire_type = ''
            if shared.get('type', None):
                wire_type = f', {remove_line_breaks(shared["type"])}'
            gauge_name = ''
            if shared.get('gauge', None):
                gauge_name = f', {shared["gauge"]} {shared["gauge_unit"]}'
            gauge_color = ''
            if 'color' in shared != '':
                gauge_color = f', {shared["color"]}'
            name = f'Wire{wire_type}{gauge_name}{gauge_color}'
            item = {'item': name,
                    'qty': round(total_length, 3),
                    'unit': self.length_unit,
                    'designators': designators,
                    'manufacturer': shared['manufacturer'],
                    'mpn': shared['mpn'],
                    'pn': shared['pn']}
            bom_cables.append(item)
            # sort list of dicts by their values
            # (https://stackoverflow.com/a/73050)
            bom_cables = sorted(bom_cables, key=lambda k: k['item'])
        bom.extend(bom_cables)

        for item in self.additional_bom_items:
            name = item['description'] if item.get('description', None) else ''
            if isinstance(item.get('designators', None), List):
                # sort designators if a list is provided
                item['designators'].sort()
            item = {'item': name,
                    'qty': item.get('qty', None),
                    'unit': item.get('unit', None),
                    'designators': item.get('designators', None),
                    'manufacturer': item.get('manufacturer', None),
                    'mpn': item.get('mpn', None),
                    'pn': item.get('pn', None)}
            bom_extra.append(item)
        bom_extra = sorted(bom_extra, key=lambda k: k['item'])
        bom.extend(bom_extra)
        return bom

    def bom_list(self):
        bom = self.bom()
        # these BOM columns will always be included
        keys = ['item', 'qty', 'unit', 'designators']
        # these optional BOM columns will only be included if at least one
        # BOM item actually uses them
        for fieldname in ['pn', 'manufacturer', 'mpn']:
            if any(fieldname in x and x.get(fieldname, None) for x in bom):
                keys.append(fieldname)
        bom_list = []
        # list of staic bom header names, headers not specified here are
        # generated by capitilising the internal name
        bom_headings = {
            "pn": "P/N",
            "mpn": "MPN"
        }
        bom_list.append([(bom_headings[k] if k in bom_headings
                          else k.capitalize())
                         for k in keys])  # create header row with keys
        for item in bom:
            # fill missing values with blanks
            item_list = [item.get(key, '') for key in keys]
            # convert any lists into comma separated strings
            item_list = [', '.join(subitem)
                         if isinstance(subitem, list) else subitem
                         for subitem in item_list]
            # if a field is missing for some (but not all) BOM items
            item_list = ['' if subitem is None else subitem
                         for subitem in item_list]
            bom_list.append(item_list)
        return bom_list

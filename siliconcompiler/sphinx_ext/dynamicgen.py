'''Sphinx extension that provides directives for automatically generating
documentation for dynamically loaded modules used by SC.
'''

from docutils import nodes
from sphinx.util.nodes import nested_parse_with_titles
from docutils.statemachine import ViewList
from sphinx.util.docutils import SphinxDirective
import docutils

import importlib
import pkgutil
import os
import subprocess

import siliconcompiler
from siliconcompiler import utils
from siliconcompiler.sphinx_ext.utils import *

#############
# Helpers
#############

# We need this in a few places, so just make it global
SC_ROOT = os.path.abspath(f'{__file__}/../../../')

def build_schema_value_table(schema, keypath_prefix=[], skip_zero_weight=False):
    '''Helper function for displaying values set in schema as a docutils table.'''
    table = [[strong('Keypath'), strong('Value')]]
    flat_cfg = flatten(schema)
    for keys, val in flat_cfg.items():
        full_keypath = list(keypath_prefix) + list(keys)

        if (skip_zero_weight and
            len(full_keypath) == 6 and full_keypath[0] == 'flowgraph' and full_keypath[-2] == 'weight' and
            'value' in val and val['value'] == '0'):
            continue

        if 'value' in val and val['value']:
            # Don't display false booleans
            if val['type'] == 'bool' and val['value'] == 'false':
                continue
            if val['type'].startswith('['):
                if len(val['value']) > 1:
                    val_node = build_list([code(v) for v in val['value']])
                elif len(val['value']) > 0:
                    val_node = code(val['value'][0])
                else:
                    val_node = para('')
            else:
                val_node = code(val['value'])

            # HTML builder fails if we don't make a text node the parent of the
            # reference node returned by keypath()
            p = nodes.paragraph()
            p += keypath(*full_keypath)
            table.append([p, val_node])

    if len(table) > 1:
        # This colspec creates two columns of equal width that fill the entire
        # page, and adds line breaks if table cell contents are longer than one
        # line. "\X" is defined by Sphinx, otherwise this is standard LaTeX.
        colspec = r'{|\X{1}{2}|\X{1}{2}|}'
        return build_table(table, colspec=colspec)
    else:
        return None

def build_config_recursive(schema, keypath_prefix=[], sec_key_prefix=[]):
    '''Helper function for displaying schema at each level as tables under nested
    sections.

    For each item:
    - If it's a leaf, collect it into a table we will display at this
        level
    - Otherwise, recurse and collect sections of lower levels
    '''
    leaves = {}
    child_sections = []
    for key, val in schema.items():
        if key == 'default': continue
        if 'help' in val:
            if 'value' in val and val['value']:
                leaves.update({key: val})
        else:
            children = build_config_recursive(val, keypath_prefix=keypath_prefix+[key], sec_key_prefix=sec_key_prefix)
            child_sections.extend(children)

    # If we've found leaves, create a new section where we'll display a
    # table plus all child sections.
    if len(leaves) > 0:
        keypath = ', '.join(keypath_prefix)
        section_key = '-'.join(sec_key_prefix + keypath_prefix)
        top = build_section(keypath, section_key)
        top += build_schema_value_table(leaves, keypath_prefix=keypath_prefix)
        top += child_sections
        return [top]
    else:
        # Otherwise, just pass on the child sections -- we don't want to
        # create an extra level of section hierarchy for levels of the
        # schema without leaves.
        return child_sections

#############
# Base class
#############

def flag_opt(argument):
    if argument is not None:
        raise ValueError('Flag should not have content')
    return True

class DynamicGen(SphinxDirective):
    '''Base class for all three directives provided by this extension.

    Each child class implements a directive by overriding the display_config()
    method and setting a PATH member variable.
    '''

    option_spec = {'nobuiltins': flag_opt}

    def document_module(self, module, modname, path):
        '''Build section documenting given module and name.'''
        print(f'Generating docs for module {modname}...')

        s = build_section_with_target(modname, f'{modname}', self.state.document)

        if not hasattr(module, 'make_docs'):
            return None

        make_docs = getattr(module, 'make_docs')

        self.generate_documentation_from_function(make_docs, path, s)

        chips = make_docs()

        if not isinstance(chips, list):
            chips = [chips]

        for chip in chips:
            extra_content = self.extra_content(chip, modname)
            if extra_content is not None:
                s += extra_content

            s += self.display_config(chip, modname)

        child_content = self.child_content(path, module, modname)
        if child_content is not None:
            s += child_content

        return s

    def run(self):
        '''Main entry point of directive.'''
        sections = []

        for module, modname in self.get_modules():
            path = module.__file__
            self.env.note_dependency(path)
            docs = self.document_module(module, modname, path)
            if docs is not None:
                sections.append((docs, modname))

        if len(sections) > 0:
            # Sort sections by module name
            sections = sorted(sections, key=lambda t: t[1])
            # Strip off modname so we just return list of docutils sections
            sections, _ = zip(*sections)

        return list(sections)

    def get_modules(self):
        '''Gets dynamic modules under `self.PATH`.

        This function explicitly searches builtins as well as SCPATH
        directories. Although the directory for builtin tools gets added to
        SCPATH after a chip object has been initialized, we can't rely on this
        since we can't be sure that's happened yet. Therefore, we have to check
        each one explicitly.

        However, this could result in duplicate modules being detected once the
        SCPATH does get updated. Therefore, we check to ensure that SCPATH
        directories are not equal to the builtins directory before searching it.

        TODO: we want better duplicate resolution (in case the user explicitly
        declares a duplicate tool), where SCPATH takes priority.
        '''
        builtins_dir = f'{SC_ROOT}/siliconcompiler/{self.PATH}'
        if 'nobuiltins' not in self.options:
            modules = self.get_modules_in_dir(builtins_dir)
        else:
            modules = []

        if 'SCPATH' in os.environ:
            scpaths = os.environ['SCPATH'].split(':')
            for scpath in scpaths:
                user_dir = f'{scpath}/{self.PATH}'
                if not os.path.isdir(user_dir) or builtins_dir == user_dir:
                    continue
                modules.extend(self.get_modules_in_dir(user_dir))

        return modules

    def get_modules_in_dir(self, module_dir):
        '''Routine for getting modules and their names from a certain
        directory.'''
        modules = []
        for importer, modname, _ in pkgutil.iter_modules([module_dir]):
            if modname in ('sc_floorplan'):
                continue
            module = importer.find_module(modname).load_module(modname)
            modules.append((module, modname))

        return modules

    def parse_rst(self, content, s):
        '''Helper for parsing reStructuredText content, adding it directly to
        section `s`.'''
        rst = ViewList()
        # use fake filename 'inline' for error # reporting
        for i, line in enumerate(content.split('\n')):
            rst.append(line, 'inline', i)
        nested_parse_with_titles(self.state, rst, s)

    def extra_content(self, chip, modname):
        '''Adds extra content to documentation.

        May return a list of docutils nodes that will be added to the
        documentation in between a module's docstring and configuration table.
        Otherwise, if return value is None, don't add anything.
        '''
        return None

    def child_content(self, path, module, modname):
        return None

    def generate_documentation_from_function(self, func, path, s):
        # raw docstrings have funky indentation (basically, each line is already
        # indented as much as the function), so we call trim() helper function
        # to clean it up
        docstr = utils.trim(func.__doc__)

        if docstr:
            self.parse_rst(docstr, s)

        builtin = os.path.abspath(path).startswith(SC_ROOT)

        if builtin:
            relpath = path[len(SC_ROOT)+1:]
            gh_root = 'https://github.com/siliconcompiler/siliconcompiler/blob/main'
            gh_link = f'{gh_root}/{relpath}'
            filename = os.path.basename(relpath)
            p = para('Setup file: ')
            p += link(gh_link, text=filename)
            s += p

#########################
# Specialized extensions
#########################

class FlowGen(DynamicGen):
    PATH = 'flows'

    def extra_content(self, chip, modname):
        flow_path = os.path.join(self.env.app.outdir, f'_images/gen/{modname}.svg')
        #chip.write_flowgraph(flow_path, fillcolor='#1c4587', fontcolor='#f1c232', border=False)
        chip.write_flowgraph(flow_path, flow=modname)
        return [image(flow_path, center=True)]

    def display_config(self, chip, modname):
        '''Display parameters under `flowgraph, <step>`, `metric, <step>` and
        `showtool`. Parameters are grouped into sections by step, with an
        additional table for non-step items.
        '''
        section_key = '-'.join(['flows', modname, 'configuration'])
        settings = build_section('Configuration', section_key)

        steps = chip.getkeys('flowgraph')
        # TODO: should try to order?

        # Build section + table for each step (combining entires under flowgraph
        # and metric)
        for step in steps:
            section_key = '-'.join(['flows', modname, step])
            section = build_section(step, section_key)
            step_cfg = {}
            for prefix in ['flowgraph']:
                cfg = chip.getdict(prefix, step)
                if cfg is None:
                    continue
                schema = Schema(cfg=cfg)
                schema.prune()
                pruned = schema.cfg
                if prefix not in step_cfg:
                    step_cfg[prefix] = {}
                step_cfg[prefix][step] = pruned

            section += build_schema_value_table(step_cfg, skip_zero_weight=True)
            settings += section

        # Build table for non-step items (just showtool for now)
        section_key = '-'.join(['flows', modname, 'option', 'showtool'])
        section = build_section('showtool', section_key)
        cfg = chip.getdict('option', 'showtool')
        schema = Schema(cfg=cfg)
        schema.prune()
        pruned = schema.cfg
        table = build_schema_value_table(pruned, keypath_prefix=['option', 'showtool'])
        if table is not None:
            section += table
            settings += section

        return settings

class PDKGen(DynamicGen):
    PATH = 'pdks'

    def display_config(self, chip, modname):
        '''Display parameters under `pdk`, `asic`, and `library` in nested form.'''

        section_key = '-'.join(['pdks', modname, 'configuration'])
        settings = build_section('Configuration', section_key)

        cfg = chip.getdict('pdk')
        settings += build_config_recursive(cfg, keypath_prefix=['pdk'], sec_key_prefix=['pdks', modname])

        return settings

class LibGen(DynamicGen):
    PATH = 'libs'

    def extra_content(self, chip, modname):
        # assume same pdk for all libraries configured by this module
        pdk = chip.get('option', 'pdk')

        p = docutils.nodes.inline('')
        pdk_ref = "None"
        if pdk:
            pdkid = get_ref_id(pdk)
            pdk_ref = f":ref:`{pdk}<{pdkid}>`"
        self.parse_rst(f'Associated PDK: {pdk_ref}', p)

        return [p]

    def display_config(self, chip, modname):
        '''Display parameters under in nested form.'''

        sections = []

        libname = chip.design

        section_key = ['lib', libname]
        settings = build_section_with_target(libname, '-'.join(section_key), self.state.document)

        for key in ('asic', 'output', 'option'):
            cfg = chip.getdict(key)
            settings += build_config_recursive(cfg, keypath_prefix=[key], sec_key_prefix=[*section_key, key])

        sections.append(settings)

        return sections

class ToolGen(DynamicGen):
    PATH = 'tools'

    def display_config(self, chip, modname):
        '''Display config under `eda, <modname>` in a single table.'''
        cfg = chip.getdict('tool', modname)
        schema = Schema(cfg=cfg)
        schema.prune()
        pruned = schema.cfg
        if 'task' in pruned:
            # Remove task specific items since they will be documented
            # by the task documentation
            del pruned['task']
        table = build_schema_value_table(pruned, keypath_prefix=['tool', modname])
        if table is not None:
            return table
        else:
            return []

    def task_display_config(self, chip, toolname, taskname):
        '''Display config under `eda, <modname>` in a single table.'''
        cfg = chip.getdict('tool', toolname, 'task', taskname)
        schema = Schema(cfg=cfg)
        schema.prune()
        pruned = schema.cfg
        table = build_schema_value_table(pruned, keypath_prefix=['tool', toolname, 'task', taskname])
        if table is not None:
            return table
        else:
            return []

    def get_modules_in_dir(self, module_dir):
        '''Custom implementation for ToolGen since the tool setup modules are
        under an extra directory, and this way we don't have to force users to
        add an __init__.py to make the directory a module itself.
        '''
        modules = []
        for toolname in os.listdir(module_dir):
            # skip over directories/files that don't match the structure of tool
            # directories (otherwise we'll get confused by Python metadata like
            # __init__.py or __pycache__/)
            if not os.path.isdir(f'{module_dir}/{toolname}'):
                continue
            path = f'{module_dir}/{toolname}/{toolname}.py'
            if not os.path.exists(path):
                continue

            spec = importlib.util.spec_from_file_location(toolname, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            modules.append((module, toolname))

        return modules

    def document_task(self, path, toolmodule, taskmodule, taskname, toolname):
        self.env.note_dependency(path)
        s = build_section_with_target(taskname, f'{toolname}-{taskname}', self.state.document)

        # Find setup function
        task_setup = getattr(taskmodule, 'setup', None)
        if not task_setup:
            return None

        # Find make_docs function, check task module first
        make_docs = getattr(taskmodule, 'make_docs', None)
        if not make_docs:
            # Then check tool module
            make_docs = getattr(toolmodule, 'make_docs', None)
        if not make_docs:
            return None

        chip = make_docs()
        # set values for current step
        chip.set('arg', 'step', '<step>')
        chip.set('arg', 'index', '<index>')
        chip.set('flowgraph', chip.get('option', 'flow'), '<step>', '<index>', 'tool', toolname)
        chip.set('flowgraph', chip.get('option', 'flow'), '<step>', '<index>', 'task', taskname)

        print(f"Generating docs for task {toolname}/{taskname}...")

        self.generate_documentation_from_function(setup, path, s)

        # Annotate the target used for default values
        if chip.valid('option', 'target') and chip.get('option', 'target'):
            p = docutils.nodes.inline('')
            target = chip.get('option', 'target')
            targetid = get_ref_id(target)
            self.parse_rst(f"Built using target: :ref:`{target}<{targetid}>`", p)
            s += p

        try:
            task_setup(chip)
            s += self.task_display_config(chip, toolname, taskname)
        except Exception as e:
            print('Failed to document task, Chip object probably not configured correctly.')
            print(e)
            return None

        return s

    def child_content(self, path, module, modname):
        sections = []
        path = os.path.abspath(path)
        module_dir = os.path.dirname(path)
        for taskfile in os.listdir(module_dir):
            if taskfile == "__init__.py":
                # skip init
                continue

            task_path = os.path.join(module_dir, taskfile)
            if path == task_path:
                # skip tool module
                continue

            if not os.path.isfile(task_path):
                # skip if not a file
                continue

            spec = importlib.util.spec_from_file_location(taskfile, task_path)
            if not spec:
                # unable to load, probably not a python file
                continue
            taskmodule = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(taskmodule)
            except:
                # Module failed to load
                # klayout imports pya which is only defined in klayout
                continue

            taskname = os.path.splitext(os.path.basename(task_path))[0]

            task_doc = self.document_task(task_path, module, taskmodule, taskname, modname)
            if task_doc:
                sections.append((taskname, task_doc))

        if len(sections) > 0:
            sections = sorted(sections, key=lambda t: t[0])
            # Strip off modname so we just return list of docutils sections
            _, sections = zip(*sections)
        return sections

class TargetGen(DynamicGen):
    PATH = 'targets'

    def build_module_list(self, chip, header, modtype, targetname, refprefix=""):
        modules = chip._loaded_modules[modtype]
        if len(modules) > 0:
            section = build_section(header, f'{targetname}-{modtype}')
            modlist = nodes.bullet_list()
            for module in modules:
                list_item = nodes.list_item()
                # TODO: replace with proper docutils nodes: sphinx.addnodes.pending_xref
                modkey = get_ref_id(refprefix+module)
                self.parse_rst(f':ref:`{module}<{modkey}>`', list_item)
                modlist += list_item

            section += modlist
            return section
        return None

    def display_config(self, chip, modname):
        sections = []

        flow_section = self.build_module_list(chip, 'Flows', 'flows', modname)
        if flow_section is not None:
            sections.append(flow_section)

        pdk_section = self.build_module_list(chip, 'PDK', 'pdks', modname)
        if pdk_section is not None:
            sections.append(pdk_section)

        libs_section = self.build_module_list(chip, 'Libraries', 'libs', modname, 'lib-')
        if libs_section is not None:
            sections.append(libs_section)

        checklist_section = self.build_module_list(chip, 'Checklists', 'checklists', modname)
        if checklist_section is not None:
            sections.append(checklist_section)

        filtered_cfg = {}
        for key in ('asic', 'constraint', 'option'):
            filtered_cfg[key] = chip.getdict(key)
        schema = Schema(cfg=filtered_cfg)
        schema.prune()
        pruned_cfg = schema.cfg

        if len(pruned_cfg) > 0:
            schema_section = build_section('Configuration', key=f'{modname}-config')
            schema_section += build_schema_value_table(pruned_cfg)
            sections.append(schema_section)

        return sections

class AppGen(DynamicGen):
    PATH = 'apps'

    def document_module(self, module, modname, path):
        # TODO: Auto-documentation does not work with apps that use 'input(...)'
        if modname in ('sc_configure'):
            return

        cmd_name = modname.replace('_', '-')
        cmd = [cmd_name, '--help']

        output = subprocess.check_output(cmd).decode('utf-8')

        section = build_section(cmd_name, cmd_name)
        section += literalblock(output)

        return section

class ExampleGen(DynamicGen):

    def get_modules(self):
        examples_dir = f'{SC_ROOT}/examples'

        modules = []
        for example in os.listdir(examples_dir):
            if not os.path.isdir(f'{examples_dir}/{example}'):
                continue
            path = f'{examples_dir}/{example}/{example}.py'
            if not os.path.exists(path):
                continue

            spec = importlib.util.spec_from_file_location(example, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            modules.append((module, example))

        return modules

    def document_module(self, module, modname, path):
        section = build_section(modname, modname)

        if not hasattr(module, 'main'):
            return None

        main = getattr(module, 'main')

        # raw docstrings have funky indentation (basically, each line is already
        # indented as much as the function), so we call trim() helper function
        # to clean it up
        docstr = utils.trim(main.__doc__)

        if docstr:
            self.parse_rst(docstr, section)

        return section

def keypath_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    # Split and clean up keypath
    keys = [key.strip() for key in text.split(',')]
    try:
        return [keypath(*keys)], []
    except ValueError as e:
        msg = inliner.reporter.error(f'{rawtext}: {e}', line=lineno)
        prb = inliner.problematic(rawtext, rawtext, msg)
        return [prb], [msg]

def setup(app):
    app.add_directive('flowgen', FlowGen)
    app.add_directive('pdkgen', PDKGen)
    app.add_directive('libgen', LibGen)
    app.add_directive('toolgen', ToolGen)
    app.add_directive('appgen', AppGen)
    app.add_directive('examplegen', ExampleGen)
    app.add_directive('targetgen', TargetGen)
    app.add_role('keypath', keypath_role)

    return {
        'version': siliconcompiler.__version__,
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }

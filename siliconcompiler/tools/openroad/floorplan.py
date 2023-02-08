
from siliconcompiler.tools.openroad.openroad import setup as setup_tool
from siliconcompiler.tools.openroad.openroad import build_pex_corners, post_process

def setup(chip):
    ''' Helper method for configs specific to floorplan tasks.
    '''

    # Generic tool setup.
    setup_tool(chip)

    tool = 'openroad'
    task = 'floorplan'
    design = chip.top()
    step = chip.get('arg', 'step')
    index = chip.get('arg', 'index')

    if chip.valid('input', 'asic', 'floorplan'):
        chip.add('tool', tool, 'task', task, 'require', ",".join(['input', 'asic', 'floorplan']), step=step, index=index)

    if (not chip.valid('input', 'netlist', 'verilog') or
        not chip.get('input', 'netlist', 'verilog')):
        chip.add('tool', tool, 'task', task, 'input', design +'.vg', step=step, index=index)

def pre_process(chip):
    build_pex_corners(chip)

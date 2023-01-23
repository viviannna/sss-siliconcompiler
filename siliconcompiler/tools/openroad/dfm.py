
from .openroad import setup as setup_tool

def setup(chip):
    ''' Helper method for configs specific to dfm tasks.
    '''

    # Generic tool setup.
    setup_tool(chip)

    tool = 'openroad'
    task = 'dfm'
    design = chip.top()
    step = chip.get('arg', 'step')
    index = chip.get('arg', 'index')

    chip.add('tool', tool, 'task', task, 'input', step, index, design +'.def')

import siliconcompiler

from siliconcompiler.tools.builtin import join


def test_nodes_to_execute():
    chip = siliconcompiler.Chip('test')
    flow = 'test'
    chip.node(flow, 'A', join)

    chip.node(flow, 'B', join)
    chip.edge(flow, 'A', 'B')

    chip.node(flow, 'C', join)
    chip.edge(flow, 'B', 'C')

    chip.node(flow, 'D', join)
    chip.edge(flow, 'A', 'D')
    chip.edge(flow, 'C', 'D')

    chip.set('option', 'flow', flow)

    chip.write_flowgraph('test_list_steps.png')

    assert chip.nodes_to_execute() == [('A', '0'), ('B', '0'), ('C', '0'), ('D', '0')]
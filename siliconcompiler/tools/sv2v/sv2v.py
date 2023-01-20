import siliconcompiler

####################################################################
# Make Docs
####################################################################
def make_docs():
    '''
    sv2v converts SystemVerilog (IEEE 1800-2017) to Verilog
    (IEEE 1364-2005), with an emphasis on supporting synthesizable
    language constructs. The primary goal of this project is to
    create a completely free and open-source tool for converting
    SystemVerilog to Verilog. While methods for performing this
    conversion already exist, they generally either rely on
    commercial tools, or are limited in scope.

    Documentation: https://github.com/zachjs/sv2v

    Sources: https://github.com/zachjs/sv2v

    Installation: https://github.com/zachjs/sv2v

    '''

    chip = siliconcompiler.Chip('<design>')
    chip.set('arg','step', '<step>')
    chip.set('arg','index', '<index>')
    setup(chip)
    return chip

def parse_version(stdout):
    # 0.0.7-130-g1aa30ea
    return '-'.join(stdout.split('-')[:-1])

##################################################
if __name__ == "__main__":

    chip = make_docs()
    chip.write_manifest("sv2v.json")

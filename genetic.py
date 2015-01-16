#!/usr/bin/python
'''
Genetic-esque optimizer.
'''
import argparse
import copy
import logging
import sys

from calculate import run_calculate
from compare import calc_x2
from datatypes import FF, MM3
from optimizer import Optimizer

logger = logging.getLogger(__name__)

class Genetic(Optimizer):
    def __init__(self):
        super(Genetic, self).__init__()
    def parse(self, args):
        parser = self.return_optimizer_parser()
        group = parser.add_argument_group('genetic')
        opts = parser.parse_args(args)
        return opts
    def run(self):
        logger.info('--- running {} ---'.format(type(self).__name__))
        if self.init_ff.x2 is None:
            self.calc_x2_ff(self.init_ff)
        # do stuff here
        if self.trial_ffs[0].x2 < self.init_ff.x2:
            self.best_ff = MM3()
            self.best_ff.method = self.trial_ffs[0].method
            self.best_ff.copy_attributes(self.init_ff)
            self.best_ff.params = copy.deepcopy(self.trial_ffs[0].params)
            self.best_ff.x2 = self.trial_ffs[0].x2
            # should never happen
            if self.trial_ffs[0].data is not None:
                self.best_ff.data = self.trial_ffs[0].data
            self.best_ff.export_ff()
            logger.info('--- {} complete ---'.format(type(self).__name__))
            logger.info('initial: {} ({})'.format(self.init_ff.x2, self.init_ff.method))
            logger.info('final: {} ({})'.format(self.best_ff.x2, self.best_ff.method))
            return self.best_ff
        else:
            self.init_ff.export_ff()
            logger.info('--- {} complete ---'.format(type(self).__name__))
            logger.info('initial: {} ({})'.format(self.init_ff.x2, self.init_ff.method))
            logger.info('final: {} ({})'.format(self.trial_ffs[0].x2, self.trial_ffs[0].method))
            logger.info('no improvement from {}'.format(type(self).__name__))
            return self.init_ff

if __name__ == '__main__':
    import logging.config
    import yaml
    with open('logging.yaml', 'r') as f:
        cfg = yaml.load(f)
    logging.config.dictConfig(cfg)
    
    genetic = Genetic()
    genetic.setup(sys.argv[1:])
    genetic.run()
    

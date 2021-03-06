#!/usr/bin/python
'''
Contains general code related to all optimization techniques.

Instead of keeping parameters in a list, we could store them based
upon their MM3* index (row, column). Then we wouldn't need to save
entire parameter sets, significantly reducing the memory usage.
'''
import argparse
import copy
import logging
import os

from calculate import run_calculate
from compare import calc_x2, import_steps
from datatypes import FF, MM3, UnallowedNegative

logger = logging.getLogger(__name__)

class Optimizer(object):
    def __init__(self):
        self.com_ref = None
        self.com_cal = None
        self.data_ref = None
        self.init_ff = None

    def central_diff_derivs(self, init_ff, central_ffs):
        for i in xrange(0, len(central_ffs), 2):
            init_ff.params[i / 2].der1 = (central_ffs[i].x2 - central_ffs[i + 1].x2) * 0.5 # 18
            init_ff.params[i / 2].der2 = central_ffs[i].x2 + central_ffs[i + 1].x2 - 2 * init_ff.x2 # 19
        logger.info('1st derivatives: {}'.format([x.der1 for x in init_ff.params]))
        logger.info('2nd derivatives: {}'.format([x.der2 for x in init_ff.params]))

    def calc_x2_ff(self, ff, save_data=False):
        self.init_ff.export_ff(params=ff.params)
        if save_data:
            ff.data = run_calculate(self.com_cal.split())
            ff.x2 = calc_x2(ff.data, self.data_ref)
        else:
            ff.x2 = calc_x2(self.com_cal, self.data_ref)
        logger.info('{}: {}'.format(ff.method, ff.x2))

    def params_diff(self, params, mode='central'):
        '''
        Perform forward or central differentiation of parameters.

        Need means of adjusting the parameter step size. When checking the parameter,
        perhaps it should account for the adjusted step size.

        I would say this function is rather memory insensitive and could
        use some improvements.
        '''
        logger.info('{} differentiation - {} parameters'.format(mode, len(params)))
        import_steps(params)
        diff_ffs = []
        for i, param in enumerate(params):
            while True:
                try:
                    ff_forward = FF()
                    ff_forward.params = copy.deepcopy(params)
                    ff_forward.method = 'forward {} {}'.format(param.mm3_row, param.mm3_col)
                    # commented region now done in compare.import_steps
                    # if isinstance(ff_forward.params[i].step, basestring):
                    #     ff_forward.params[i].value += ff_forward.params[i].value * \
                    #         float(ff_forward.params[i].step)
                    # else:
                    #     ff_forward.params[i].value += ff_forward.params[i].step
                    ff_forward.params[i].value += ff_forward.params[i].step
                    ff_forward.params[i].check_value()
                    if mode == 'central':
                        ff_backward = FF()
                        ff_backward.method = 'backward {} {}'.format(param.mm3_row, param.mm3_col)
                        ff_backward.params = copy.deepcopy(params)
                        ff_backward.params[i].value -= ff_backward.params[i].step
                        ff_backward.params[i].check_value()
                except UnallowedNegative as e:
                    logger.warning(e.message)
                    logger.warning('changing step size of {} from {} to {}'.format(
                            param, param.step, param.value * 0.05))
                    param.step = param.value * 0.05
                else:
                    ff_forward.display_params()
                    diff_ffs.append(ff_forward)
                    if mode == 'central':
                        ff_backward.display_params()
                        diff_ffs.append(ff_backward)
                    break
        logger.info('generated {} force fields for {} differentiation'.format(len(diff_ffs), mode))
        return diff_ffs

    def return_optimizer_parser(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--calculate', '-c', type=str,
                            metavar='" commands for calculate.py"',
                            help=('These commands produce the calculated data. Leave one space '
                                  'after the 1st quotation mark enclosing the arguments.'))
        parser.add_argument('--directory', '-d', type=str, metavar='directory', default=os.getcwd(),
                            help='Directory where data and force field files are located.')
        parser.add_argument('--ptypes', '-pt', type=str, nargs='+')
        parser.add_argument('--pfile', '-pf', type=str)
        parser.add_argument('--reference', '-r', type=str,
                            metavar='" commands for calculate.py"',
                            help=('These commands produce the reference data. Leave one space '
                                  'after the 1st quotation mark enclosing the arguments.'))
        return parser

    def setup(self, args):
        opts = self.parse(args)
        logger.info('--- setup {} ---'.format(type(self).__name__))
        self.com_ref = opts.reference
        self.com_cal = opts.calculate
        self.init_ff = MM3(os.path.join(opts.directory, 'mm3.fld'))
        self.init_ff.import_ff()
        self.init_ff.method = 'initial'
        logger.info('{} ff loaded from {} - {} parameters'.format(
                self.init_ff.method, self.init_ff.path, len(self.init_ff.params)))

        params_to_optimize = []
        if opts.ptypes:
            params_to_optimize.extend([x for x in self.init_ff.params if x.ptype in opts.ptypes])
        if opts.pfile:
            with open(os.path.join(opts.directory, opts.pfile), 'r') as f:
                for line in f:
                    line = line.partition('#')[0]
                    cols = line.split()
                    if cols:
                        mm3_row, mm3_col = int(cols[0]), int(cols[1])
                        allow_negative = None
                        for arg in cols[2:]:
                            if any(arg == x for x in ('allowneg', 'neg', 'negative')):
                                allow_negative = True
                                logger.log(7, 'param {} {} allowed negative values'.format(
                                        mm3_row, mm3_col))
                        for param in self.init_ff.params:
                            if mm3_row == param.mm3_row and mm3_col == param.mm3_col:
                                param._allow_negative = allow_negative
                                params_to_optimize.append(param)
        for param in params_to_optimize:
            param.check_value()
        # import_steps(params_to_optimize)
        self.init_ff.params = params_to_optimize
        logger.info('{} parameters selected for optimization'.format(len(self.init_ff.params)))

        self.data_ref = run_calculate(self.com_ref.split())
        
        return opts

    def trim_params_on_2nd(self, params):
        '''
        Returns a new list of parameters containing the ones that have
        the lowest 2nd derivatives with respect to the objective
        function. Doesn't modify the input parameter list.
        '''
        params_sorted = sorted(params, key=lambda x: x.der2)
        params_to_keep = params_sorted[:self.max_params]
        if len(params_sorted) != len(params_to_keep):
            logger.info('reduced number of parameters from {} to {} based on 2nd derivatives'.format(
                    len(params_sorted), len(params_to_keep)))
            logger.info('2nd derivatives: {}'.format([x.der2 for x in params_to_keep]))
        return params_to_keep

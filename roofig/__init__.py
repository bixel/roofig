from itertools import product
import numpy as np
import pandas as pd

from ROOT import RooRealVar, RooCategory


class ConfigurationError(Exception):
    pass


class FitParameters():
    class RealVar():
        def __init__(self, *args):
            self.var = RooRealVar(args[0], args[0], *args[1:])

        @property
        def min(self):
            return self.var.getMin()

        @min.setter
        def min(self, val):
            self.var.setMin(val)

        @property
        def val(self):
            return self.var.getVal()

        @property
        def max(self):
            return self.var.getMax()

        @max.setter
        def max(self, val):
            self.var.setMax(val)

        def __getattr__(self, name):
            return getattr(self.var, name)

        def __repr__(self):
            ret = f'RooRealVar {self.var.GetName()} = {self.var.getVal()}'
            if not self.var.isConstant():
                ret += f' [{self.min}, {self.max}]'
            return ret

    def __init__(self):
        self.param_list = set()

    def __setattr__(self, name, value):
        if hasattr(self, name):
            if type(value) in [int, float]:
                getattr(self, name).setVal(value)
                return
            else:
                print(f'warning: overriding "{name}"')
        super().__setattr__(name, value)

    @property
    def r(self):
        class bag():
            pass

        params = bag()
        for name in self.param_list:
            param = getattr(self, name)
            if type(param) == FitParameters.RealVar:
                setattr(params, name, param.var)
            elif type(param) == RooCategory:
                setattr(params, name, param)
        return params

    def add_param(self, name, *args):
        param = FitParameters.RealVar(name, *args)
        self.param_list.add(name)
        setattr(self, name, param)

    def expand_params(self, template, *args, **kwargs):
        names = kwargs.keys()
        values = kwargs.values()
        for parameter_values in product(*values):
            name = template.format(
                **{n: v
                   for n, v in zip(names, parameter_values)})
            self.add_param(name, *args)

    def add_observable(self, name, *args, values=None):
        if values is None and not args:
            raise ConfigurationError('Need to define either values or default '
                                     'RooRealVar args.')
        if values is not None:
            min, max = np.min(values), np.max(values)
            self.add_param(name, min, max)
        else:
            self.add_param(name, *args)

    def add_category(self, name, values):
        cat = RooCategory(name, name)
        for val in pd.unique(values):
            cat.defineType(str(val), int(val))
        self.param_list.add(name)
        setattr(self, name, cat)

    def pop(self, key, default_value=None):
        if key in self.param_list:
            self.param_list.remove(key)
        return self.__dict__.pop(key, default_value)

    def glob(self, expr):
        from fnmatch import fnmatch
        return [getattr(self, p) for p in self.param_list if fnmatch(p, expr)]

    def __repr__(self):
        string = f'Parameter collection\n{len(self.param_list)} parameters:'
        for p in sorted(list(self.param_list)):
            parameter = getattr(self, p)
            string += f'\n{p}'
            if parameter.isConstant():
                string += '\tconst'
            elif type(parameter) == RooRealVar:
                string += f'\t{getattr(self, p).getMin():.2g}'
                string += f'\t{getattr(self, p).getMax():.2g}'
        return string


class Plotter:
    def __init__(self, sampling_steps=1000):
        self.sampling_steps = sampling_steps

    def sample_pdf(self, pdf, variable, norm=None):
        import ROOT as R
        from scipy.integrate import trapz

        """
        for some reason, pdf.plotOn yields the correct pdf while scanning
        does not work as expected...
        """
        xs = []
        ys = []
        curve = pdf.plotOn(variable.frame(),
                           R.RooFit.Precision(1e-5)).getCurve()
        for x in np.linspace(variable.getMin(), variable.getMax(),
                             self.sampling_steps):
            variable.setVal(x)
            xs.append(x)

            # still need to interpolate to get the same shape everywhere
            ys.append(curve.interpolate(x))

        xs, ys = np.array([xs, ys])

        if norm is not None:
            integral = trapz(ys, xs)
            ys /= integral
            ys *= norm

        return xs, ys

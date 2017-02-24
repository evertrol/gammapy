# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import absolute_import, division, print_function, unicode_literals
import numpy as np
import astropy.units as u
from astropy.io import fits
from astropy.table import Table
from ..extern.bunch import Bunch
from ..utils.nddata import NDDataArray, DataAxis, BinnedDataAxis
from ..utils.energy import EnergyBounds
from ..utils.scripts import make_path
from ..utils.fits import fits_table_to_table, table_to_fits_table

__all__ = [
    'EffectiveAreaTable',
    'EffectiveAreaTable2D',
]


class EffectiveAreaTable(object):
    """Effective Area Table

    TODO: Document

    Parameters
    -----------
    energy_lo : `~astropy.units.Quantity`
        Lower bin edges of energy axis
    energy_hi : `~astropy.units.Quantity`
        Upper bin edges of energy axis
    data : `~astropy.units.Quantity`
        Effective area

    Examples
    --------
    Plot parametrized effective area for HESS, HESS2 and CTA.

    .. plot::
        :include-source:

        import numpy as np
        import matplotlib.pyplot as plt
        import astropy.units as u
        from gammapy.irf import EffectiveAreaTable

        energy = np.logspace(-3, 3, 100) * u.TeV

        for instrument in ['HESS', 'HESS2', 'CTA']:
            aeff = EffectiveAreaTable.from_parametrization(energy, instrument)
            ax = aeff.plot(label=instrument)

        ax.set_yscale('log')
        ax.set_xlim([1e-3, 1e3])
        ax.set_ylim([1e3, 1e12])
        plt.legend(loc='best')
        plt.show()

    Find energy where the effective area is at 10% of its maximum value

    >>> import numpy as np
    >>> from gammapy.irf import EffectiveAreaTable
    >>> import astropy.units as u
    >>> energy = np.logspace(-1,2) * u.TeV
    >>> aeff_max = aeff.max_area
    >>> print(aeff_max).to('m2')
    156909.413371 m2
    >>> ener = aeff.find_energy(0.1 * aeff_max)
    >>> print(ener)
    0.185368478744 TeV
    """
    def __init__(self, energy_lo, energy_hi, data, meta=None):
        axes = [BinnedDataAxis(energy_lo, energy_hi,
                               interpolation_mode='log', name='energy')]
        self.data = NDDataArray(axes=axes, data=data)
        if meta is not None:
            self.meta = Bunch(meta)

    @property
    def energy(self):
        return self.data.axis('energy')

    def plot(self, ax=None, energy=None, show_energy=None, **kwargs):
        """Plot effective area

        Parameters
        ----------
        ax : `~matplotlib.axes.Axes`, optional
            Axis
        energy : `~astropy.units.Quantity`
            Energy nodes
        show_energy : `~astropy.units.Quantity`, optional
            Show energy, e.g. threshold, as vertical line

        Returns
        -------
        ax : `~matplotlib.axes.Axes`
            Axis

        """
        import matplotlib.pyplot as plt
        ax = plt.gca() if ax is None else ax

        kwargs.setdefault('lw', 2)

        if energy is None:
            energy = self.energy.nodes
        eff_area = self.data.evaluate(energy=energy)
        xerr = (energy.value - self.energy.lo.value,
                self.energy.hi.value - energy.value)
        ax.errorbar(energy.value, eff_area.value, xerr=xerr, **kwargs)
        if show_energy is not None:
            ener_val = u.Quantity(show_energy).to(self.energy.unit).value
            ax.vlines(ener_val, 0, 1.1 * self.max_area.value,
                      linestyles='dashed')
        ax.set_xscale('log')
        ax.set_xlabel('Energy [{}]'.format(self.energy.unit))
        ax.set_ylabel('Effective Area [{}]'.format(self.data.data.unit))

        return ax

    @classmethod
    def from_parametrization(cls, energy, instrument='HESS'):
        """Get parametrized effective area

        Parametrizations of the effective areas of different Cherenkov
        telescopes taken from Appendix B of Abramowski et al. (2010), see
        http://adsabs.harvard.edu/abs/2010MNRAS.402.1342A .

        .. math::
            A_{eff}(E) = g_1 \\left(\\frac{E}{\\mathrm{MeV}}\\right)^{-g_2}\\exp{\\left(-\\frac{g_3}{E}\\right)}

        Parameters
        ----------
        energy : `~astropy.units.Quantity`
            Energy binning, analytic function is evaluated at log centers
        instrument : {'HESS', 'HESS2', 'CTA'}
            Instrument name
        """
        energy = EnergyBounds(energy)
        # Put the parameters g in a dictionary.
        # Units: g1 (cm^2), g2 (), g3 (MeV)
        # Note that whereas in the paper the parameter index is 1-based,
        # here it is 0-based
        pars = {'HESS': [6.85e9, 0.0891, 5e5],
                'HESS2': [2.05e9, 0.0891, 1e5],
                'CTA': [1.71e11, 0.0891, 1e5]}

        if instrument not in pars.keys():
            ss = 'Unknown instrument: {0}\n'.format(instrument)
            ss += 'Valid instruments: HESS, HESS2, CTA'
            raise ValueError(ss)

        xx = energy.log_centers.to('MeV').value

        g1 = pars[instrument][0]
        g2 = pars[instrument][1]
        g3 = -pars[instrument][2]

        value = g1 * xx ** (-g2) * np.exp(g3 / xx)

        data = value * u.cm ** 2

        return cls(energy_lo=energy.lower_bounds,
                   energy_hi = energy.upper_bounds, data=data)

    @classmethod
    def from_table(cls, table):
        """ARF reader"""
        energy_col = 'ENERG'
        data_col = 'SPECRESP'

        energy_lo = table['{}_LO'.format(energy_col)].quantity
        energy_hi = table['{}_HI'.format(energy_col)].quantity
        data = table['{}'.format(data_col)].quantity
        return cls(energy_lo=energy_lo, energy_hi=energy_hi, data=data)

    @classmethod
    def from_hdulist(cls, hdulist, hdu='SPECRESP'):
        fits_table = hdulist[hdu]
        table = fits_table_to_table(fits_table)
        return cls.from_table(table)

    @classmethod
    def read(cls, filename, hdu='SPECRESP', **kwargs):
        filename = make_path(filename)
        hdulist = fits.open(str(filename), **kwargs)
        try:
            return cls.from_hdulist(hdulist, hdu=hdu)
        except KeyError:
            msg = 'File {} contains no HDU "{}"'.format(filename, hdu)
            msg += '\n Available {}'.format([_.name for _ in hdulist])
            raise ValueError(msg)

    def to_table(self):
        """Convert to `~astropy.table.Table`

        http://gamma-astro-data-formats.readthedocs.io/en/latest/ogip/index.html#arf-file
        """
        ener_lo = self.energy.lo
        ener_hi = self.energy.hi
        data = self.evaluate_fill_nan()
        names = ['ENERG_LO', 'ENERG_HI', 'SPECRESP']
        meta = dict(name='SPECRESP', hduclass='OGIP', hduclas1='RESPONSE',
                    hduclas2='SPECRESP')
        return Table([ener_lo, ener_hi, data], names=names, meta=meta)

    def to_hdulist(self):
        hdu = table_to_fits_table(self.to_table())
        prim_hdu = fits.PrimaryHDU()
        return fits.HDUList([prim_hdu, hdu])

    def write(self, filename, **kwargs):
        filename = make_path(filename)
        self.to_hdulist().writeto(str(filename), **kwargs)

    def evaluate_fill_nan(self, **kwargs):
        """Modified evalute function

        Calls :func:`gammapy.utils.nddata.NDDataArray.evaluate` and replaces
        possible nan values. Below the finite range the effective area is set
        to zero and above to value of the last valid note. This is needed since
        other Sofwares, e.g. sherpa, don't like nan values in FITS files. Make
        sure that the replacement happens outside of the energy range, where
        the `~gammapy.irf.EffectiveAreaTable` is used.
        """
        retval = self.data.evaluate(**kwargs)
        idx = np.where(np.isfinite(retval))[0]
        retval[np.arange(idx[0])] = 0
        retval[np.arange(idx[-1], len(retval))] = retval[idx[-1]]
        return retval

    @property
    def max_area(self):
        """Maximum effective area"""
        cleaned_data = self.data.data[np.where(~np.isnan(self.data.data))]
        return cleaned_data.max()

    def find_energy(self, aeff):
        """Find energy for given effective area

        A linear interpolation is performed between the two nodes closest to
        the desired effective area value.

        TODO: Move to `~gammapy.utils.nddata.NDDataArray`

        Parameters
        ----------
        aeff: `~astropy.units.Quantity`
            Effective area value

        Returns
        -------
        energy: `~astropy.units.Quantity`
            Energy corresponing to aeff
        """
        idx = np.where(self.data.data > aeff)[0][0]

        # Linear interpolation between two energy nodes
        energy = np.interp(aeff.value,
                           (self.data.data[[idx - 1, idx]].value),
                           (self.energy.nodes[[idx - 1, idx]].value))
        return energy * self.energy.unit

    def to_sherpa(self, name):
        """Return `~sherpa.astro.data.DataARF`

        Parameters
        ----------
        name : str
            Instance name
        """
        from sherpa.astro.data import DataARF

        table = self.to_table()
        kwargs = dict(
            name = name,
            energ_lo = table['ENERG_LO'].quantity.to('keV').value,
            energ_hi = table['ENERG_HI'].quantity.to('keV').value,
            specresp = table['SPECRESP'].quantity.to('cm2').value,
        )

        return DataARF(**kwargs)


class EffectiveAreaTable2D(object):
    """2D Effective Area Table

    Parameters
    -----------
    energy_lo : `~astropy.units.Quantity`
        Lower bin edges of energy axis
    energy_hi : `~astropy.units.Quantity`
        Upper bin edges of energy axis
    offset_lo : `~astropy.units.Quantity`
        Lower bin edges of offset axis
    offset_hi : `~astropy.units.Quantity`
        Upper bin edges of offset axis
    data : `~astropy.units.Quantity`
        Effective area
    low_threshold : `~astropy.units.Quantity`, optional 
        Low energy threshold
    high_threshold : `~astropy.units.Quantity`, optional 
        High energy threshold

    Examples
    --------
    Create `~gammapy.irf.EffectiveAreaTable2D` from scratch

    >>> from gammapy.irf import EffectiveAreaTable2D
    >>> import astropy.units as u
    >>> import numpy as np
    >>> energy = np.logspace(0,1,11) * u.TeV
    >>> offset = np.linspace(0,1,4) * u.deg
    >>> data = np.ones(shape=(10,4)) * u.cm * u.cm
    >>> eff_area = EffectiveAreaTable2D(energy=energy, offset=offset, data= data)
    >>> print(eff_area)
    Data array summary info
    energy         : size =    11, min =  1.000 TeV, max = 10.000 TeV
    offset         : size =     4, min =  0.000 deg, max =  1.000 deg
    Data           : size =    40, min =  1.000 cm2, max =  1.000 cm2
    """

    def __init__(self, energy_lo, energy_hi, offset_lo, offset_hi, data, meta=None):
        axes = [
            BinnedDataAxis(
                energy_lo, energy_hi, 
                interpolation_mode='log', name='energy'),
            BinnedDataAxis(
                offset_lo, offset_hi,
                interpolation_mode='linear', name='offset')
        ]
        self.data = NDDataArray(axes=axes, data=data)
        if meta is not None:
            self.meta = Bunch(meta)

    @property
    def energy(self):
        return self.data.axis('energy')

    @property
    def offset(self):
        return self.data.axis('offset')

    @property
    def low_threshold(self):
        """Low energy threshold"""
        return self.meta.LO_THRES * u.TeV

    @property
    def high_threshold(self):
        """High energy threshold"""
        return self.meta.HI_THRES * u.TeV

    @classmethod
    def from_table(cls, table):
        """This is a reader for the format specified at
        http://gamma-astro-data-formats.readthedocs.io/en/latest/irfs/effective_area/index.html#aeff-2d-format
        """
        energy_col = 'ENERG'
        offset_col = 'THETA'
        data_col = 'EFFAREA'

        energy_lo = table['{}_LO'.format(energy_col)].quantity[0]
        energy_hi = table['{}_HI'.format(energy_col)].quantity[0]
        o_lo = table['{}_LO'.format(offset_col)].quantity[0]
        o_hi = table['{}_HI'.format(offset_col)].quantity[0]
        data = table['{}'.format(data_col)].quantity[0].transpose()
        return cls(offset_lo=o_lo, offset_hi=o_hi,
                   energy_lo=energy_lo, energy_hi=energy_hi, 
                   data=data, meta=table.meta)

    @classmethod
    def from_hdulist(cls, hdulist, hdu='EFFECTIVE AREA'):
        fits_table = hdulist[hdu]
        table = fits_table_to_table(fits_table)
        return cls.from_table(table)

    @classmethod
    def read(cls, filename, hdu='EFFECTIVE AREA'):
        filename = make_path(filename)
        hdulist = fits.open(str(filename))
        try:
            return cls.from_hdulist(hdulist, hdu=hdu)
        except KeyError:
            msg = 'File {} contains no HDU "{}"'.format(filename, hdu)
            msg += '\n Available {}'.format([_.name for _ in hdulist])
            raise ValueError(msg)

    def to_effective_area_table(self, offset, energy=None):
        """Evaluate at a given offset and return `~gammapy.irf.EffectiveAreaTable`

        Parameters
        ----------
        offset : `~astropy.coordinates.Angle`
            Offset
        energy : `~astropy.units.Quantity`
            Energy axis bin edges
        """
        if energy is None:
            energy = self.energy.bins
       
        energy = EnergyBounds(energy)

        area = self.data.evaluate(offset=offset, energy=energy.log_centers)
        return EffectiveAreaTable(energy_lo=energy.lower_bounds,
                                  energy_hi=energy.upper_bounds,
                                  data=area)

    def plot_energy_dependence(self, ax=None, offset=None, energy=None, **kwargs):
        """Plot effective area versus energy for a given offset.

        Parameters
        ----------
        ax : `~matplotlib.axes.Axes`, optional
            Axis
        offset : `~astropy.coordinates.Angle`
            Offset
        energy : `~astropy.units.Quantity`
            Energy axis
        kwargs : dict
            Forwarded tp plt.plot()

        Returns
        -------
        ax : `~matplotlib.axes.Axes`

            Axis
        """
        import matplotlib.pyplot as plt

        ax = plt.gca() if ax is None else ax

        if offset is None:
            off_min, off_max = self.data.axis('offset').nodes[[0, -1]].value
            offset = np.linspace(off_min, off_max, 4) * self.data.axis('offset').unit

        if energy is None:
            energy = self.energy.nodes

        for off in offset:
            area = self.data.evaluate(offset=off, energy=energy)
            label = 'offset = {:.1f}'.format(off)
            ax.plot(energy, area.value, label=label, **kwargs)

        ax.set_xscale('log')
        ax.set_xlabel('Energy [{0}]'.format(self.energy.unit))
        ax.set_ylabel('Effective Area [{0}]'.format(self.data.data.unit))
        ax.set_xlim(min(energy.value), max(energy.value))
        ax.legend(loc='upper left')

        return ax

    def plot_offset_dependence(self, ax=None, offset=None, energy=None, **kwargs):
        """Plot effective area versus offset for a given energy

        Parameters
        ----------
        ax : `~matplotlib.axes.Axes`, optional
            Axis
        offset : `~astropy.coordinates.Angle`
            Offset axis
        energy : `~gammapy.utils.energy.Energy`
            Energy

        Returns
        -------
        ax : `~matplotlib.axes.Axes`
            Axis
        """
        import matplotlib.pyplot as plt

        ax = plt.gca() if ax is None else ax

        if energy is None:
            e_min, e_max = np.log10(self.energy.nodes[[0, -1]].value)
            energy = np.logspace(e_min, e_max, 4) * self.energy.unit

        if offset is None:
            off_lo, off_hi = self.data.axis('offset').nodes[[0, -1]].to('deg').value
            offset = np.linspace(off_lo, off_hi, 100) * u.deg

        for ee in energy:
            area = self.data.evaluate(offset=offset, energy=ee)
            area /= np.nanmax(area)
            if np.isnan(area).all():
                continue
            label = 'energy = {:.1f}'.format(ee)
            ax.plot(offset, area, label=label, **kwargs)

        ax.set_ylim(0, 1.1)
        ax.set_xlabel('Offset ({0})'.format(self.data.axis('offset').unit))
        ax.set_ylabel('Relative Effective Area')
        ax.legend(loc='best')

        return ax

    def plot_image(self, ax=None, offset=None, energy=None, **kwargs):
        """Plot effective area image.
        """
        import matplotlib.pyplot as plt

        kwargs.setdefault('cmap', 'afmhot')
        kwargs.setdefault('origin', 'bottom')
        kwargs.setdefault('interpolation', 'nearest')

        ax = plt.gca() if ax is None else ax

        if offset is None:
            vals = self.data.axis('offset').nodes.value
            offset = np.linspace(vals.min(), vals.max(), 100)
            offset = offset * self.data.axis('offset').unit

        if energy is None:
            vals = np.log10(self.energy.nodes.value)
            energy = np.logspace(
                vals.min(), vals.max(), 100) * self.energy.unit

        aeff = self.data.evaluate(offset=offset, energy=energy)
        extent = [
            offset.value.min(), offset.value.max(),
            energy.value.min(), energy.value.max(),
        ]
        ax.imshow(aeff.value, extent=extent, **kwargs)

        ax.set_yscale('log')
        ax.set_xlabel('Offset ({0})'.format(offset.unit))
        ax.set_ylabel('Energy ({0})'.format(energy.unit))

        ax.set_title('Effective Area ({0})'.format(aeff.unit))

        ax.legend()

        return ax

    def peek(self, figsize=(15, 5)):
        """Quick-look summary plots."""
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(nrows=1, ncols=3, figsize=figsize)
        self.plot_image(ax=axes[0])
        self.plot_energy_dependence(ax=axes[1])
        self.plot_offset_dependence(ax=axes[2])
        plt.tight_layout()

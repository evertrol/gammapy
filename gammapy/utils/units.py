# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Units and Quantity related helper functions"""
import logging
import astropy.units as u
import numpy as np
from math import floor

__all__ = ["standardise_unit", "unit_from_fits_image_hdu"]

log = logging.getLogger(__name__)


def standardise_unit(unit):
    """Standardise unit.

    Changes applied by this function:

    * Drop "photon" == "ph" from the unit
    * Drop "count" == "ct" from the unit

    Parameters
    ----------
    unit : `~astropy.units.Unit` or str
        Any old unit

    Returns
    -------
    unit : `~astropy.units.Unit`
        Shiny new, standardised unit

    Examples
    --------
    >>> from gammapy.utils.units import standardise_unit
    >>> standardise_unit('ph cm-2 s-1')
    Unit("1 / (cm2 s)")
    >>> standardise_unit('ct cm-2 s-1')
    Unit("1 / (cm2 s)")
    >>> standardise_unit('cm-2 s-1')
    Unit("1 / (cm2 s)")
    """
    unit = u.Unit(unit)
    bases, powers = [], []
    for base, power in zip(unit.bases, unit.powers):
        if str(base) not in {"ph", "ct"}:
            bases.append(base)
            powers.append(power)

    return u.CompositeUnit(scale=unit.scale, bases=bases, powers=powers)


def unit_from_fits_image_hdu(header):
    """Read unit from a FITS image HDU.

    - The ``BUNIT`` key is used.
    - `astropy.units.Unit` is called.
      If the ``BUNIT`` value is invalid, a log warning
      is emitted and the empty unit is used.
    - `standardise_unit` is called
    """
    unit = header.get("BUNIT", "")

    try:
        u.Unit(unit)
    except ValueError:
        log.warning(f"Invalid value BUNIT={unit!r} in FITS header. Setting empty unit.")
        unit = ""

    return standardise_unit(unit)

def energy_str_formatting(E):
    """
    Format energy quantities to a string representation that is more comfortable to read
    by swithcing to the most relevant unit (keV, MeV, GeV, TeV) and changing the float precision.
    Parameters
    ----------    
    E: `~astropy.units.Quantity`
        Scalar Quantity.
    Returns
    -------
    str : str
        Returns a string with energy unit formatted        
    """    
    i = floor(np.log10(E.to_value(u.eV)) / 3) # a new unit every 3 decades
    unit = (u.eV, u.keV, u.MeV, u.GeV, u.TeV, u.PeV)[i] if i < 5 else u.PeV        

    v = E.to_value(unit)
    i=floor(np.log10(v))
    prec = (2,1,0)[i] if i < 3 else 0

    return f"{v:0.{prec}f} {unit}"

def energy_unit_format(E):
    """
    Format an energy quantity (or a list of quantities) to a string (or list of string) representations.
    Parameters
    ----------    
    E: `~astropy.units.Quantity` or sequence thereof
        Quantity or list of quantities
    Returns
    -------
    str : str
        Returns a string or list of strings with energy unit formatted        
    """   

    if (isinstance(E, (list, tuple)) == True):
        E_fmt = [energy_str_formatting(e) for e in E]
        return E_fmt        
    elif (isinstance(E, u.quantity.Quantity) == True):
        if E.size > 1:
            E_fmt = [energy_str_formatting(e) for e in E]
            return E_fmt                      
        else:
            return energy_str_formatting(E)
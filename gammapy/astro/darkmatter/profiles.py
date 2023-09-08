# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Dark matter profiles."""
import abc
import numpy as np
import astropy.units as u
from gammapy.modeling import Parameter, Parameters
from gammapy.utils.integrate import trapz_loglog

__all__ = [
    "BurkertProfile",
    "DMProfile",
    "EinastoProfile",
    "IsothermalProfile",
    "MooreProfile",
    "NFWProfile",
    "ZhaoProfile",
]


class DMProfile(abc.ABC):
    """DMProfile model base class."""

    LOCAL_DENSITY = 0.3 * u.GeV / (u.cm**3)
    """Local dark matter density as given in refenrece 2"""
    DISTANCE_GC = 8.33 * u.kpc
    """Distance to the Galactic Center as given in reference 2"""

    def __call__(self, radius):
        """Call evaluate method of derived classes."""
        kwargs = {par.name: par.quantity for par in self.parameters}
        return self.evaluate(radius, **kwargs)

    def scale_to_local_density(self):
        """Scale to local density."""
        scale = (self.LOCAL_DENSITY / self(self.DISTANCE_GC)).to_value("")
        self.parameters["rho_s"].value *= scale

    def _eval_squared(self, radius, separation):
        """Squared density at given radius together with the substitution part"""
        return (
            self(radius) ** 2
            * radius
            / np.sqrt(radius**2 - (self.DISTANCE_GC * np.sin(separation)) ** 2)
        )

    def integral(self, rmin, rmax, separation, ndecade):
        r"""Integrate squared dark matter profile numerically.

        .. math::
            F(r_{min}, r_{max}) = \int_{r_{min}}^{r_{max}}\rho(r)^2 dr

        Parameters
        ----------
        rmin, rmax : `~astropy.units.Quantity`
            Lower and upper bound of integration range.
        separation : `~numpy.ndarray`
            Separation angle in rad
        ndecade    : int, optional
            Number of grid points per decade used for the integration.
            Default : 10000
        """
        integral = self.integrate_spectrum_separation(
            self._eval_squared, rmin, rmax, separation, ndecade
        )
        return integral.to("GeV2 / cm5")

    def integrate_spectrum_separation(self, func, xmin, xmax, separation, ndecade):
        r"""Helper for the squared dark matter profile integral.

        Parameters
        ----------
        xmin, xmax : `~astropy.units.Quantity`
            Lower and upper bound of integration range.
        separation : `~numpy.ndarray`
            Separation angle in rad
        ndecade    : int
            Number of grid points per decade used for the integration.
        """
        unit = xmin.unit
        xmin = xmin.value
        xmax = xmax.to_value(unit)
        logmin = np.log10(xmin)
        logmax = np.log10(xmax)
        n = np.int32((logmax - logmin) * ndecade)
        x = np.logspace(logmin, logmax, n) * unit
        y = func(x, separation)
        val = trapz_loglog(y, x)
        return val.sum()


class ZhaoProfile(DMProfile):
    r"""Zaho Profile.
    .. math::
        \rho(r) = \rho_s \left(\frac{r_s}{r}\right)^\gamma \left(1 + \left(\frac{r}{r_s}\right)^\alpha \right)^{\frac{\gamma - \beta}{\alpha}}

    Parameters
    ----------
    r_s : `~astropy.units.Quantity`
        Scale radius, :math:`r_s`
    alpha : `~astropy.units.Quantity`
        :math:`\alpha`
    beta: `~astropy.units.Quantity`
        :math:`\beta`
    gamma : `~astropy.units.Quantity`
        :math:`\gamma`
    rho_s : `~astropy.units.Quantity`
        Characteristic density, :math:`\rho_s`

    References
    ----------
    * `1996MNRAS.278..488Z <https://ui.adsabs.harvard.edu/abs/1996MNRAS.278..488Z>`_
    * `2011JCAP...03..051 <https://ui.adsabs.harvard.edu/abs/2011JCAP...03..051>`_
    """

    DEFAULT_SCALE_RADIUS = 24.42 * u.kpc
    DEFAULT_ALPHA = 1
    DEFAULT_BETA = 3
    DEFAULT_GAMMA = 1
    """
    (alpha, beta, gamma) = (1,3,1) is NFW profile.
    Default scale radius as given in reference 2 (same as for NFW profile)
    """

    def __init__(
        self, r_s=None, alpha=None, beta=None, gamma=None, rho_s=1 * u.Unit("GeV / cm3")
    ):
        r_s = self.DEFAULT_SCALE_RADIUS if r_s is None else r_s
        alpha = self.DEFAULT_ALPHA if alpha is None else alpha
        beta = self.DEFAULT_BETA if beta is None else beta
        gamma = self.DEFAULT_GAMMA if gamma is None else gamma
        self.parameters = Parameters(
            [
                Parameter("r_s", u.Quantity(r_s)),
                Parameter("rho_s", u.Quantity(rho_s)),
                Parameter("alpha", alpha),
                Parameter("beta", beta),
                Parameter("gamma", gamma),
            ]
        )

    @staticmethod
    def evaluate(radius, r_s, alpha, beta, gamma, rho_s):
        rr = radius / r_s
        return rho_s / (rr**gamma * (1 + rr**alpha) ** ((beta - gamma) / alpha))


class NFWProfile(DMProfile):
    r"""NFW Profile.

    .. math::
        \rho(r) = \rho_s \frac{r_s}{r}\left(1 + \frac{r}{r_s}\right)^{-2}

    Parameters
    ----------
    r_s : `~astropy.units.Quantity`
        Scale radius, :math:`r_s`
    rho_s : `~astropy.units.Quantity`
        Characteristic density, :math:`\rho_s`

    References
    ----------
    * `1997ApJ...490..493 <https://ui.adsabs.harvard.edu/abs/1997ApJ...490..493N>`_
    * `2011JCAP...03..051 <https://ui.adsabs.harvard.edu/abs/2011JCAP...03..051>`_
    """

    DEFAULT_SCALE_RADIUS = 24.42 * u.kpc
    """Default scale radius as given in reference 2"""

    def __init__(self, r_s=None, rho_s=1 * u.Unit("GeV / cm3")):
        r_s = self.DEFAULT_SCALE_RADIUS if r_s is None else r_s
        self.parameters = Parameters(
            [Parameter("r_s", u.Quantity(r_s)), Parameter("rho_s", u.Quantity(rho_s))]
        )

    @staticmethod
    def evaluate(radius, r_s, rho_s):
        rr = radius / r_s
        return rho_s / (rr * (1 + rr) ** 2)


class EinastoProfile(DMProfile):
    r"""Einasto Profile.

    .. math::
        \rho(r) = \rho_s \exp{
            \left(-\frac{2}{\alpha}\left[
            \left(\frac{r}{r_s}\right)^{\alpha} - 1\right] \right)}

    Parameters
    ----------
    r_s : `~astropy.units.Quantity`
        Scale radius, :math:`r_s`
    alpha : `~astropy.units.Quantity`
        :math:`\alpha`
    rho_s : `~astropy.units.Quantity`
        Characteristic density, :math:`\rho_s`

    References
    ----------
    * `1965TrAlm...5...87E <https://ui.adsabs.harvard.edu/abs/1965TrAlm...5...87E>`_
    * `2011JCAP...03..051 <https://ui.adsabs.harvard.edu/abs/2011JCAP...03..051>`_
    """

    DEFAULT_SCALE_RADIUS = 28.44 * u.kpc
    """Default scale radius as given in reference 2"""
    DEFAULT_ALPHA = 0.17
    """Default scale radius as given in reference 2"""

    def __init__(self, r_s=None, alpha=None, rho_s=1 * u.Unit("GeV / cm3")):
        alpha = self.DEFAULT_ALPHA if alpha is None else alpha
        r_s = self.DEFAULT_SCALE_RADIUS if r_s is None else r_s

        self.parameters = Parameters(
            [
                Parameter("r_s", u.Quantity(r_s)),
                Parameter("alpha", u.Quantity(alpha)),
                Parameter("rho_s", u.Quantity(rho_s)),
            ]
        )

    @staticmethod
    def evaluate(radius, r_s, alpha, rho_s):
        rr = radius / r_s
        exponent = (2 / alpha) * (rr**alpha - 1)
        return rho_s * np.exp(-1 * exponent)


class IsothermalProfile(DMProfile):
    r"""Isothermal Profile.

    .. math:: \rho(r) = \frac{\rho_s}{1 + (r/r_s)^2}

    Parameters
    ----------
    r_s : `~astropy.units.Quantity`
        Scale radius, :math:`r_s`

    References
    ----------
    * `1991MNRAS.249..523B <https://ui.adsabs.harvard.edu/abs/1991MNRAS.249..523B>`_
    * `2011JCAP...03..051 <https://ui.adsabs.harvard.edu/abs/2011JCAP...03..051>`_
    """

    DEFAULT_SCALE_RADIUS = 4.38 * u.kpc
    """Default scale radius as given in reference 2"""

    def __init__(self, r_s=None, rho_s=1 * u.Unit("GeV / cm3")):
        r_s = self.DEFAULT_SCALE_RADIUS if r_s is None else r_s

        self.parameters = Parameters(
            [Parameter("r_s", u.Quantity(r_s)), Parameter("rho_s", u.Quantity(rho_s))]
        )

    @staticmethod
    def evaluate(radius, r_s, rho_s):
        rr = radius / r_s
        return rho_s / (1 + rr**2)


class BurkertProfile(DMProfile):
    r"""Burkert Profile.

    .. math:: \rho(r) = \frac{\rho_s}{(1 + r/r_s)(1 + (r/r_s)^2)}

    Parameters
    ----------
    r_s : `~astropy.units.Quantity`
        Scale radius, :math:`r_s`

    References
    ----------
    * `1995ApJ...447L..25B <https://ui.adsabs.harvard.edu/abs/1995ApJ...447L..25B>`_
    * `2011JCAP...03..051 <https://ui.adsabs.harvard.edu/abs/2011JCAP...03..051>`_
    """

    DEFAULT_SCALE_RADIUS = 12.67 * u.kpc
    """Default scale radius as given in reference 2"""

    def __init__(self, r_s=None, rho_s=1 * u.Unit("GeV / cm3")):
        r_s = self.DEFAULT_SCALE_RADIUS if r_s is None else r_s

        self.parameters = Parameters(
            [Parameter("r_s", u.Quantity(r_s)), Parameter("rho_s", u.Quantity(rho_s))]
        )

    @staticmethod
    def evaluate(radius, r_s, rho_s):
        rr = radius / r_s
        return rho_s / ((1 + rr) * (1 + rr**2))


class MooreProfile(DMProfile):
    r"""Moore Profile.

    .. math::
        \rho(r) = \rho_s \left(\frac{r_s}{r}\right)^{1.16}
        \left(1 + \frac{r}{r_s} \right)^{-1.84}

    Parameters
    ----------
    r_s : `~astropy.units.Quantity`
        Scale radius, :math:`r_s`

    References
    ----------
    * `2004MNRAS.353..624D <https://ui.adsabs.harvard.edu/abs/2004MNRAS.353..624D>`_
    * `2011JCAP...03..051 <https://ui.adsabs.harvard.edu/abs/2011JCAP...03..051>`_
    """

    DEFAULT_SCALE_RADIUS = 30.28 * u.kpc
    """Default scale radius as given in reference 2"""

    def __init__(self, r_s=None, rho_s=1 * u.Unit("GeV / cm3")):
        r_s = self.DEFAULT_SCALE_RADIUS if r_s is None else r_s

        self.parameters = Parameters(
            [Parameter("r_s", u.Quantity(r_s)), Parameter("rho_s", u.Quantity(rho_s))]
        )

    @staticmethod
    def evaluate(radius, r_s, rho_s):
        rr = radius / r_s
        rr_ = r_s / radius
        return rho_s * rr_**1.16 * (1 + rr) ** (-1.84)

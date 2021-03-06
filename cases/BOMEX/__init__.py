import warnings

import numpy as np

from .. import BaseCase

def _interpolate(z, datapoints):
    return np.interp(z, datapoints[:,0], datapoints[:,1])

class BOMEX(BaseCase):
    """
    Based on the "undisturbed period" of phase 3 of the Barbados Oceanographic
    and Meteorological Experiment (BOMEX). 
    
    From Siebesma et al 2003:
        "This is a trade wind cumulus case whose behavior was observed to be
        remarkably steady, and for which there were no apparent complications
        from precipitation or mesoscale circulations", "... the BOMEX case has
        large-scale forcings whose net effect is to essentially compensate
        the integrated effect of the surface fluxes and radiative forcings..."

    The profiles below are taken from Table B1 of the Siebesma et al 2003 and
    "are based on rawinsonde data from the _Oceanographer_, the most northern
    ship of the BOMEX square, averaged over 22 and 23 June 1969, during which a
    well-defined steady state was capped by a pronounced trade wind inversion.
    Given the surface pressure, other mean profiles such as pressure, absolute
    temperature, etc., can be easily deduced assuming hydrostatic equilibrium."

    """
    SCITATION_REF = "Siebesma et al 2003"
    FORCING_IS_TRANSIENT = False

    def __init__(self, include_wind=True):
        self.include_wind = include_wind
        if include_wind:
            self.u_wind = self._u_wind
            self.v_wind = self._v_wind
        else:
            self.u_wind = lambda z: np.zeros_like(z)
            self.v_wind = lambda z: np.zeros_like(z)

        # surface conditions
        self.ps = 101500. # [Pa], surface pressure
        self.p0 = 100000. # [Pa], reference pressure, XXX: I'm not certain about this, not in the paper
        self.Ts = 300.375 # [K], sea surface temperature

        # constants
        self.Lv = 2.5e6  # [J/kg]
        self.c_p = 1005. # [J/kg/K]
        self.g = 9.81    # [m/s^2]
        self.R_d = 287.  # [J/kg/K]

        self.z_max = 3e3

        self.f = 0.376e-4 # [1/s], Coriolis parameter

        self._create_profile()
        self._calc_surface_reference_state()

    def _calc_surface_reference_state(self):
        cp_d = self.c_p
        Rd = self.R_d

        p = self.p0
        T = self.Ts
        qv = self.q_t(z=0.0)

        # NB: these constants don't appear to be given in Siebesma et al
        Rv = 461.51
        cp_v = 1859.0

        qd = 1.0 - qv
        R = qv*Rv + qd*Rd
        rho = p/T*1.0/R
        cp = qd*cp_d + qv*cp_v

        self.R0 = R
        self.rho0 = rho
        self.cp0 = cp


    # forcings

    @np.vectorize
    def wtheta_sfc_flx():
        """Surface flux of potential temperature [K*m/s]"""
        return 8.0e-3

    @np.vectorize
    def wqt_sfc_flx():
        """Surface flux of total water [kg/kg*m/s]"""
        return 5.2e-5

    @np.vectorize
    def velw_sfc_flx(u, v, w):
        """Surface momentum flux [m^2/s^2]"""
        u_star = 0.28 # [m/s]

        U_mag = np.linalg.norm([u, v, w], axis=1)
        assert U_mag.shape == u.shape

        return -u_star**2. * np.array([u/U_mag, v/U_mag, w/U_mag])

    def lh_surf_flux(self):
        """
        Surface latent heat flux in [W/m^2]
        """
        return self.rho0*self.Lv*self.wqt_sfc_flx()

    def sh_surf_flux(self):
        """
        Surface latent heat flux in [W/m^2]
        """
        return self.rho0*self.cp0*self.wtheta_sfc_flx()


    # initial conditions

    def q_t(self, z):
        """ Total water specific concentration [kg/kg]"""
        return self._q_t(z)/1000.

    @np.vectorize
    def _q_t(z):
        datapoints = np.array([
            [0.,    17.0],
            [520.,  16.3],
            [1480., 10.7],
            [2000., 4.2],
            [3000., 3.0],
        ])

        return _interpolate(z=z, datapoints=datapoints)

    @np.vectorize
    def theta_l(z):
        """ Liquid water potential temperature [K]"""
        datapoints = np.array([
            [0.,    298.7],
            [520.,  298.7],
            [1480., 302.4],
            [2000., 308.2],
            [3000., 311.85],
        ])

        return _interpolate(z=z, datapoints=datapoints)

    @np.vectorize
    def _u_wind(z):
        """
        u-component of wind
        """
        datapoints = np.array([
            [0.,    -8.75],
            [700.,  -8.75],
            [3000., -4.61],
        ])

        return _interpolate(z=z, datapoints=datapoints)

    @np.vectorize
    def _v_wind(z):
        """
        v-component of wind
        """
        return z*0.0

    @np.vectorize
    def ddt_theta_l__ls(z):
        """
        Large Scale Horizontal Liq. Water Pot. Temperature Advection combined
        with Radiative Cooling [K/s] 
        """
        datapoints = np.array([
            [0.,    -2.0],
            [300.,  -2.0],
            [1500.,  0.0],
            [3000.,  0.0],
        ])

        return _interpolate(z=z, datapoints=datapoints)

    @np.vectorize
    def ddt_qv_ls(z):
        """
        Large Scale Horizontal Moisture Advection [(kg/kg)/s]
        """
        datapoints = np.array([
            [0.,    -1.2],
            [300.,  -1.2],
            [500.,  0.0],
            [3000., 0.0],
        ])

        return 1.0e-8 * _interpolate(z=z, datapoints=datapoints)

    @np.vectorize
    def w_subsidence(z):
        """
        Large Scale Subsidence w [m/s] Apply the subsidence on the prognostic
        fields of q_t, theta_l.

        OBS: Siebesma et all 2003 list subsidence with units of [cm/s]
        """
        datapoints = np.array([
            [0.,    0.0],
            [1500., -0.65],
            [2100., 0.0],
            [3000., 0.0],
        ])

        return 1.0e-2 * _interpolate(z=z, datapoints=datapoints)

    @np.vectorize
    def tke(z):
        """Initial subgrid profile of subgrid TKE [m^2/s^2]"""
        return  1 - z/3000.

    @np.vectorize
    def u_g(z):
        """u-component of geostrophic wind [m/s]"""
        return -10. + 1.0e-3*z

    @np.vectorize
    def v_g(z):
        """v-component of geostrophic wind [m/s]"""
        return 0.0*z

    @np.vectorize
    def generate_theta_l_field(z):
        """Generate a theta_l [K] field including initial random perturbations"""
        dtheta_l = 0.1 # [K]
        return BOMEX.theta_l(z) + dtheta_l*(np.random.random(z.shape) - 0.5)

    @np.vectorize
    def generate_q_t_field(z):
        """Generate a q_t [kg/kg] field including initial random perturbations"""
        dq_t = 2.5e-2*1.0e-3 # [kg/kg]
        return BOMEX.q_t(z) + dq_t*(np.random.random(z.shape) - 0.5)

    def _create_profile(self):
        """ Create a vertical profile that we can interpolate into later. 
        Integrating with the hydrostatic assumption.
        """
        try:
            from pyclouds import parameterisations
        except ImportError:
            warnings.warn("pyclouds module couldn't be found, can't create"
                    "profile for interpolation of rho, T, RH and p")
            return

        parameterisation = parameterisations.SaturationVapourPressure()

        # XXX: R_v and cp_v are not given in the RICO test definition on the
        # the KNMI site I will use what I believe are standard values here
        self.R_v = parameterisations.common.default_constants.get('R_v')
        self.cp_v = parameterisations.common.default_constants.get('cp_v')

        dz = 100.
        R_d = self.R_d

        R_v = self.R_v
        R_d = self.R_d
        cp_d = self.c_p
        cp_v = self.cp_v

        z = 0.0
        p = self.ps

        profile = []

        n = 0
        while z < self.z_max:
            qt = self.q_t(z)

            # assume no liquid water
            ql = 0.0
            qv = qt

            qd = 1.0 - qt

            theta_l = self.theta_l(z)

            R_l = R_d*qd + R_v*qv
            c_l = cp_d*qd + cp_v*qv

            T = theta_l/((self.p0/p)**(R_l/c_l))


            qv_sat = parameterisation.qv_sat(T=T, p=p)
            assert qt < qv_sat

            rho = 1.0/((qd*R_d + qv*R_v)*T/p) # + 1.0/(ql/rho_l), ql = 0.0

            profile.append((z, rho, p, T))

            # integrate pressure
            z += dz
            p += - rho * self.g * dz

            n += 1

        self._profile = np.array(profile)


    def _get_value_from_precomputed_profile(self, z, var_indx):
        z = self._profile[:,0]
        if np.any(z > self.z_max):
            raise Exception("{} test case is only defined for z < {}km".format(str(self), self.z_max/1000.))
        T = self._profile[:,var_indx]
        return np.interp(z, z, T)

    def rho(self, z):
        return self._get_value_from_precomputed_profile(z, 1)

    def p(self, z):
        return self._get_value_from_precomputed_profile(z, 2)

    def temp(self, z):
        return self._get_value_from_precomputed_profile(z, 3)

    def rel_humidity(self, z):
        q_v = self.q_t(z)
        p = self.p(z)
        T = self.temp(z)

        from pyclouds import parameterisations
        parameterisation = parameterisations.SaturationVapourPressure()

        qv_sat = parameterisation.qv_sat(T=T, p=p)

        return q_v/qv_sat

    def __str__(self):
        ext = [' without with', ''][self.include_wind]
        return super(BOMEX, self).__str__() + ext

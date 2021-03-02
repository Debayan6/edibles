import numpy as np
from scipy.special import wofz
from scipy.interpolate import interp1d
import astropy.constants as cst
import matplotlib.pyplot as plt
from edibles import PYTHONDIR
from edibles.utils.edibles_oracle import EdiblesOracle
from edibles.utils.edibles_spectrum import EdiblesSpectrum
from pathlib import Path
import pandas as pd
from scipy.ndimage import gaussian_filter


def voigt_profile(x, sigma, gamma):
    """
    Function to return the value of a (normalized) Voigt profile centered at x=0
    and with (Gaussian) width sigma and Lorentz damping (=HWHM) gamma.

    The Voigt profile is computed using the scipy.special.wofz, which returns
    the value of the Faddeeva function.


    WARNING
    scipy.special.wofz is not compaible with np.float128 type parameters.

    Args:
        x (float64): Scalar or array of x-values
        sigma (float64): Gaussian sigma component
        gamma (float64): Lorentzian gamma (=HWHM) component

    Returns:
        ndarray: Flux array for given input

    """

    z = (x + 1j * gamma) / sigma / np.sqrt(2)

    return np.real(wofz(z)) / sigma / np.sqrt(2 * np.pi)


def voigt_optical_depth(wave, lambda0=0.0, b=0.0, N=0.0, f=0.0, gamma=0.0, v_rad=0.0):

    """
    Function to return the value of a Voigt optical depth profile at a given wavelength, for a line
    centered at lambda0.

    Args:
        wave (float64): Wavelength at which optical depth is to be calculatd (in Angstrom)
        lambda0 (float64): Central (rest) wavelength for the absorption line, in Angstrom.
        b (float64): The b parameter (Gaussian width), in km/s.
        N (float64): The column density (in cm^{-2})
        f (float64): The oscillator strength (dimensionless)
        gamma (float64): Lorentzian gamma (=HWHM) component
        v_rad (float64): Radial velocity of absorption line (in km/s)

    Returns:
        float64: Optical Depth at wave.

    """

    # All we have to do is proper conversions so that we feed the right numbers into the call
    # to the VoigtProfile -- see documentation for details.
    nu = cst.c.to("angstrom/s").value / wave
    nu0 = cst.c.to("angstrom/s").value / lambda0
    sigma = (b * 1e13) / lambda0 / np.sqrt(2)
    gamma_voigt = gamma / 4 / pi
    tau_factor = (N * pi * cst.e.esu ** 2 / cst.m_e.cgs / cst.c.cgs * f).value

    # print("Nu0 is:        " + "{:e}".format(nu0))
    # print("Sigma is:      " + "{:e}".format(sigma))
    # print("Gamma is:      " + "{:e}".format(gamma_voigt))
    # print("Tau_factor is: " + "{:e}".format(tau_factor))

    # Transform this into a frequency grid centered around nu0

    ThisVoigtProfile = voigt_profile(nu - nu0, sigma, gamma_voigt)
    tau = tau_factor * ThisVoigtProfile

    return tau


def voigt_absorption_line(
    wavegrid, lambda0=0.0, f=0.0, gamma=0.0, b=0.0, N=0.0, v_rad=0.0, v_resolution=0.0
):
    """
    Function to return a complete Voigt Absorption Line Model, smoothed to the specified
    resolution and resampled to the desired wavelength grid.
    This can in fact be a set of different absorption lines -- same line, different
    cloud components or different line for single cloud component.

    Args:
        wavegrid (float64): Wavelength grid (in Angstrom) on which the final result is desired.
        lambda0 (float64): Central (rest) wavelength for the absorption line, in Angstrom.
        b (float64): The b parameter (Gaussian width), in km/s.
        N (float64): The column density (in cm^{-2})
        f (float64): The oscillator strength (dimensionless)
        gamma (float64): Lorentzian gamma (=HWHM) component
        v_rad (float64): Radial velocity of absorption line (in km/s)
        v_resolution (float64): Instrument resolution in velocity space (in km/s)

    Returns:
        ndarray: Normalized flux for specified grid & parameters.

    """
    # Let's convert the parameters to numpy arrays first.
    lambda0_array = np.array(lambda0, ndmin=1)
    f_array = np.array(f, ndmin=1)
    gamma_array = np.array(gamma, ndmin=1)
    b_array = np.array(b, ndmin=1)
    N_array = np.array(N, ndmin=1)
    v_rad_array = np.array(v_rad, ndmin=1)

    # How many lines are passed on?
    n_lines = lambda0_array.size
    print("Number of lines: " + "{:d}".format(n_lines))

    # How many cloud components do we have?
    n_components = N_array.size
    print("Number of components: " + "{:d}".format(n_components))

    # We will consider 3 different cases here:
    # 1. A single line, but multiple components.
    #    --> Each component represents a cloud; use the same spectral line parameters for each
    #        component. We will set that up here, and then do a recursive call to
    #        voigt_absorption_line.
    # 2. Multiple lines, but a single component.
    #    --> E.g. the Na doublet lines. For each line component, we will use the same
    #        cloud components. We will set that up here, and then do a recursive call
    #        to voigt_absorption_line.
    # 3. Multiple lines, and multiple components.
    #    Here, we consider 2 different cases:
    #    A) If n_lines == n_components, we will treat each combination as a unique, single line.
    #       We could have gotten here from the recursive calls in 1. and 2. Exception: if the
    #       keyword /MultiCloud is set. In that case we will proceed as in B).
    #    B) If n_lines <> n_components, we will interpret this as meaning that each
    #       component will produce each of the lines. This means we now have to create
    #       n_lines * n_components entries for the recursive call. We will set that up here.

    if (n_lines == 1) & (n_components != 1):
        # Case 1 from above. Replicate all the line parameters for each of the components,
        # and issue the call to self.
        lambda0_use = np.repeat(lambda0, n_components)
        f_use = np.repeat(f, n_components)
        gamma_use = np.repeat(gamma, n_components)
        # we should really check whether we have the correct number of other parameters....
        interpolated_model = voigt_absorption_line(
            wavegrid,
            lambda0=lambda0_use,
            f=f_use,
            gamma=gamma_use,
            b=b,
            N=N,
            v_rad=v_rad,
            v_resolution=v_resolution,
        )
    elif (n_components == 1) & (n_lines != 1):
        # Case 2 from above. Replicate all the sightline parameters for each of the lines,
        # and issue the call to self.
        b_use = np.repeat(b, n_lines)
        N_use = np.repeat(N, n_lines)
        v_rad_use = np.repeat(v_rad, n_lines)
        interpolated_model = voigt_absorption_line(
            wavegrid,
            lambda0=lambda0,
            f=f,
            gamma=gamma,
            b=b_use,
            N=N_use,
            v_rad=v_rad_use,
            v_resolution=v_resolution,
        )
    elif n_lines == n_components:
        # Case 3A from above.
        print("Number of components: ", n_lines)
        # We can process each line/component now with its own set of parameters.
        # We will loop over each line, create the proper wavelength grid, then get the
        # corresponding optical depth profile, and then decide how to combine everything.
        #
        # One thing to ensure though is that the step size in velocity space is the same for
        # each component -- otherwise the Gaussian smoothing at the end will go wrong.
        # So determine the step size first, based on the smallest b value.
        v_stepsize = b_array.min() / 10

        # We will also need to be able to add each optical depth profile, so we need a common
        # wavelength grid to interpolate on. Let's use a width of 20 * b for each line, and see
        # what wavelength limits to consider.
        bluewaves = lambda0_array * (
            1.0 + (v_rad_array - 20.0 * b_array) / cst.c.to("km/s").value
        )
        redwaves = lambda0_array * (
            1.0 + (v_rad_array + 20.0 * b_array) / cst.c.to("km/s").value
        )
        minwave = bluewaves.min()
        maxwave = redwaves.max()
        print(lambda0_array)
        print(v_rad_array)
        print(bluewaves)
        print("Wave range: ", minwave, maxwave)
        n_v = int(
            np.ceil((maxwave - minwave) / minwave * cst.c.to("km/s").value / v_stepsize)
        )
        refgrid = minwave * (1.0 + np.arange(n_v) * v_stepsize / cst.c.to("km/s").value)
        allcomponents = np.zeros(shape=(n_v, n_lines))

        for lineloop in range(n_lines):
            v_limits = [-20.0 * b_array[lineloop], 20.0 * b_array[lineloop]]
            dv = np.arange(
                start=v_limits[0], stop=v_limits[1], step=v_stepsize
            )  # in km/s
            thiswavegrid = lambda0_array[lineloop] * (1.0 + dv / cst.c.to("km/s").value)
            tau = voigt_optical_depth(
                thiswavegrid,
                lambda0=lambda0_array[lineloop],
                b=b_array[lineloop],
                N=N_array[lineloop],
                f=f_array[lineloop],
                gamma=gamma_array[lineloop],
                v_rad=v_rad_array[lineloop],
            )
            # Shift to the proper wavelength given the radial velocity
            vel = dv + v_rad_array[lineloop]
            thiswavegrid = lambda0_array[lineloop] * (
                1.0 + vel / cst.c.to("km/s").value
            )
            # Interpolate to reference grid
            interpolationfunction = interp1d(
                thiswavegrid, tau, kind="cubic", fill_value="extrapolate"
            )
            tau_grid = interpolationfunction(refgrid)
            tau_grid[np.where(refgrid > np.max(thiswavegrid))] = 0
            tau_grid[np.where(refgrid < np.min(thiswavegrid))] = 0
            allcomponents[:, lineloop] = tau_grid

        # Now add up all the optical depth components.
        tau = np.sum(allcomponents, axis=1)

        # plt.plot(refgrid,tau_coadd)
        # plt.gca().get_xaxis().get_major_formatter().set_useOffset(False)
        # plt.show()

        # Do the radiative transfer
        AbsorptionLine = np.exp(-tau)

        # Apply a Gaussian instrumental smoothing function!
        # Calculate sigma -- in units of step size!
        smooth_sigma = fwhm2sigma(v_resolution) / v_stepsize
        # print("Smoothing sigma is: " + "{:e}".format(smooth_sigma))
        gauss_smooth = gaussian_filter(AbsorptionLine, sigma=smooth_sigma)
        interpolationfunction = interp1d(
            refgrid, gauss_smooth, kind="cubic", bounds_error=False, fill_value=(1, 1)
        )
        interpolated_model = interpolationfunction(wavegrid)
        # plt.plot(refgrid, AbsorptionLine, marker='o')
        # plt.plot(refgrid, gauss_smooth, color='green', marker='D')
        # plt.plot(wavegrid,interpolated_model, color='red', marker='1')
        # plt.show()
    else:
        # Create arrays that hold all the lines for all the components. 
        # We need in total n_components * n_lines array elements. 
        lambda0_use = np.repeat(lambda0, n_components)
        f_use = np.repeat(f, n_components)
        gamma_use = np.repeat(gamma, n_components)
        # For the eomponents, do some dimensional juggling.... 
        b_use = np.concatenate(np.repeat([b], n_lines, axis=0), axis=0)
        N_use = np.concatenate(np.repeat([N], n_lines, axis=0), axis=0)
        v_rad_use = np.concatenate(np.repeat([v_rad], n_lines, axis=0), axis=0)
        #print(lambda0_use)
        #print(N_use)
        interpolated_model = voigt_absorption_line(
            wavegrid,
            lambda0=lambda0_use,
            f=f_use,
            gamma=gamma_use,
            b=b_use,
            N=N_use,
            v_rad=v_rad_use,
            v_resolution=v_resolution,
        )
            #"voigt_absorption_line Panic: This option has not been implemented yet.... "
        #)

    return interpolated_model


def fwhm2sigma(fwhm):
    """
    Simple function to convert a Gaussian FWHM to Gaussian sigma.
    """
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    return sigma


#  --------------------------------------------------------------------------------------


if __name__ == "__main__":

    from math import *

    """
    This is a series of examples / tests to see if the implementation of the various Voigt
    functions has been done correctly. It includes tests for the basic Voigt function, as
    well as for the various forms of the normalized Voigt profiles. One test aims to
    reproduce the high-resolution profile for the K line of omi Per (form Welty et al.)
    """
    show_example = 4

    if show_example == 1:
        #############################################################
        #
        # EXAMPLE 1: a single line.
        #
        #############################################################
        wavegrid = np.arange(1000) * 0.01 + 5000
        AbsorptionLine = voigt_absorption_line(
            wavegrid,
            lambda0=5003.0,
            b=0.75,
            N=1e11,
            f=1,
            gamma=1e7,
            v_rad=-10.0,
            v_resolution=0.26,
        )
        plt.plot(wavegrid, AbsorptionLine, marker="1")
        plt.gca().get_xaxis().get_major_formatter().set_useOffset(False)
        plt.show()

    elif show_example == 2:
        #############################################################
        #
        # EXAMPLE 2: Single line, multiple cloud components.
        #
        #############################################################
        # This, in fact, is reproducing Dan Welty's high-resolution
        # observations of the K line of o Per.
        folder = Path(PYTHONDIR + "/data")
        filename = folder / "voigt_benchmarkdata" / "omiper.m95.7698.txt"
        Headers = ["Wavelength", "Normfluxval"]
        omiper_data = pd.read_csv(
            filename,
            delim_whitespace=True,
            skiprows=[0],
            header=None,
            names=Headers,
            engine="python",
        )

        lambda0 = 7698.974  # K wavelength in angstrom.
        f = 3.393e-1  # oscillator strength
        gamma = 3.8e7  # Gamma for K line
        b = [0.60, 0.44, 0.72, 0.62, 0.60]  # b parameter in km/s
        N = np.array([12.5, 10.0, 44.3, 22.5, 3.9]) * 1e10  # Column density
        v_rad = (
            np.array([10.50, 11.52, 13.45, 14.74, 15.72]) + 0.1
        )  # Radial velocity of cloud in km/s
        v_resolution = 0.56  # Instrumental resolution in km / s

        AbsorptionLine = voigt_absorption_line(
            omiper_data["Wavelength"],
            lambda0=lambda0,
            b=b,
            N=N,
            f=f,
            gamma=gamma,
            v_rad=v_rad,
            v_resolution=v_resolution,
        )

        plt.plot(
            omiper_data["Wavelength"],
            omiper_data["Normfluxval"],
            marker="D",
            fillstyle="none",
            color="black",
        )
        plt.gca().get_xaxis().get_major_formatter().set_useOffset(False)
        plt.xlim(7699.15, 7699.45)
        plt.plot(omiper_data["Wavelength"], AbsorptionLine, color="orange", marker="+")
        plt.show()

    elif show_example == 3:
        #############################################################
        #
        # EXAMPLE 3: Na doublet: multiple lines, single cloud.
        #
        #############################################################

        # Let's see if we can reproduce the Na lines for HD 145502
        lambda0 = [3302.369, 3302.978]
        f = [8.26e-03, 4.06e-03]
        gamma = [6.280e7, 6.280e7]
        b = [0.8]
        N = [1.8e13]
        v_rad = 18.9
        v_resolution = 5.75

        pythia = EdiblesOracle()
        List = pythia.getFilteredObsList(
            object=["HD 145502"], MergedOnly=True, Wave=3302.0
        )
        test = List.values.tolist()
        filename = test[0]
        print(filename)
        wrange = [3301.5, 3304.0]
        sp = EdiblesSpectrum(filename)
        wave = sp.wave
        flux = sp.flux
        idx = np.where((wave > wrange[0]) & (wave < wrange[1]))
        wave = wave[idx]
        flux = flux[idx]
        flux = flux / np.median(flux)
        AbsorptionLine = voigt_absorption_line(
            wave,
            lambda0=lambda0,
            b=b,
            N=N,
            f=f,
            gamma=gamma,
            v_rad=v_rad,
            v_resolution=v_resolution,
        )
        plt.plot(wave, flux)
        plt.gca().get_xaxis().get_major_formatter().set_useOffset(False)
        plt.plot(wave, AbsorptionLine, color="orange", marker="*")
        plt.show()
    
    elif show_example == 4:
        #############################################################
        #
        # EXAMPLE 4: Na doublet: multiple lines, multiple cloud.
        #
        #############################################################

        # Let's see if we can reproduce the Na lines for HD 145502
        lambda0 = [3302.369, 3302.978]
        f = [8.26e-03, 4.06e-03]
        gamma = [6.280e7, 6.280e7]
        b = [1.0, 1.4, 1.4]
        N = [1e13, 1.5e14, 5.0e14]
        v_rad = [1.0, 8.0, 22.0]
        v_resolution = 5.75

        pythia = EdiblesOracle()
        List = pythia.getFilteredObsList(object=["HD 183143"], MergedOnly=True, Wave=3302.0)
        test = List.values.tolist()
        filename = test[0]
        print(filename)
        wrange = [3301.5, 3304.0]
        sp = EdiblesSpectrum(filename)
        wave = sp.wave
        flux = sp.flux
        idx = np.where((wave > wrange[0]) & (wave < wrange[1]))
        wave = wave[idx]
        flux = flux[idx]
        flux = flux / np.median(flux)
        AbsorptionLine = voigt_absorption_line(
            wave,
            lambda0=lambda0,
            b=b,
            N=N,
            f=f,
            gamma=gamma,
            v_rad=v_rad,
            v_resolution=v_resolution,
        )
        plt.plot(wave, flux)
        plt.gca().get_xaxis().get_major_formatter().set_useOffset(False)
        plt.plot(wave, AbsorptionLine, color="orange", marker="*")
        plt.show()
    
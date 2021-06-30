"""Module to simulate the PQR- branches of a molecule with known symmetry."""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import ConnectionPatch
import pandas as pd
from astropy import constants as const
from astropy import units as u
from astropy.convolution import Gaussian1DKernel, convolve
from edibles.utils.voigt_profile import voigt_optical_depth

pd.options.mode.chained_assignment = None
c = const.c.to('km/s')
kms = (u.km / u.s)


def WavelengthToWavenumber(values):
    """Convert wavelength to wavenumber.

    Args:
        values (1darray): Array with wavelengths

    Returns:
        wavenumbers (1darray): Array with wavenumbers.
    """
    wavenumbers = 1/(values*(10**-8))
    return(wavenumbers)


class Rotational_Energies:
    """Simulate the PQR-branches of a molecule with known symmetry.

    Args:
        A (float): Rotational constant of the first rotational axis.
        B (float): Constant of the second axis.
        C (float): Constant of the third axis.
        Target (str): Name of the target sightline.
        Q_scale (float): Scale of the Q-branch.
        PR_scale (float): Scale of the P-branch and R-branch.
    """

    def __init__(self, A, B, C, Target, Q_scale, PR_scale):
        """Init the Rotational_Energies class."""
        # print('init')
        self.A = A
        self.B = B
        self.C = C
        self._determine_symmetry_type()
        self.Target = Target
        self.Q_scale = Q_scale
        self.PR_scale = PR_scale

    def _determine_symmetry_type(self):
        """Get symmetry type accordingly with the rotational constants."""
        self.flag = False

        # An spherical symmetry has the same rotational constant for all axes.
        if self.A == self.B == self.C:
            self.symmetry_type = 'spherical'

        # Prolate  and oblate symmetries has two rotational constant with same value

        # The unique constant is bigger in a prolate symmetry.
        elif self.B == self.C and self.A > self.B:
            self.symmetry_type = 'symmetric_prolate'

        # The unique constant is smaller in an oblate symmetry.
        elif self.B == self.A and self.B > self.C:
            self.symmetry_type = 'symmetric_oblate'

        else:
            self.symmetry_type = 'asymmetric'
            print('Asymmetric tops are too hard for me to deal with right now!')

            # Flag to stop processing.
            self.flag = True

        print('Symmetry Type: ', self.symmetry_type)

    def rotational_energies(self, Jlimit):
        """Compute the rotational energy values.

        Calculate the rotational energy values for all the possible
        combinations of the rotational quantum numbers.

        Args:
            Jlimit (int): Upper bound of the first rotational quantum number J.
        """
        # print("Calculating rotational energy values")
        self.Jlimit = Jlimit

        if self.symmetry_type == 'spherical':

            # Values of the quantum rotational number.
            J = np.arange(0, self.Jlimit+1)

            # Energy of each J value.
            E = self.B*J*(J+1)

            # Empty values for K.
            K = np.nan

        else:

            # Possible values of the first and second quantum rotational numbers (J and K).
            J_vals = np.arange(0, self.Jlimit+1)
            K_vals = np.arange(-self.Jlimit, self.Jlimit+1)

            # Generate all possible combinations.
            J, K = np.array(np.meshgrid(J_vals, K_vals)).T.reshape(-1, 2).T

            # Energy of each (J, K) pair of a prolate symmetry.
            if self.symmetry_type == 'symmetric_prolate':
                E = self.B*J*(J+1) + (self.A-self.B)*K**2

            # Energy of each (J, K) pair of an oblate symmetry.
            elif self.symmetry_type == 'symmetric_oblate':
                E = self.B*J*(J+1)+(self.C-self.B)*K**2

        self.K = pd.Series(K)
        self.J = pd.Series(J)
        self.E = pd.Series(E)

    def boltzmann(self, T):
        """Compute the Boltzmann distribution.

        Calculate the state population using the Boltzann distribution for
        a given temperature.

        Args:
            T (float): Temperature (Kelvin degrees).
        """
        # print("Calculating state population")
        h = const.h.value
        c = const.c.to('cm/s').value
        k = const.k_B.value

        self.T = T
        exponent = (-h*c*self.B*self.J*(self.J+1)*(1/(k*T))).astype('float64')
        self.population = (2*self.J+1)*np.exp(exponent)

        # Renormalize
        norm_pop = self.population/(np.sum(self.population))
        self.population = pd.Series(norm_pop)

    def allowed_combinations(self, Jup, Kup, Eup, Q_Branch=False):
        """Determine allowed transitions.

        Determine allowed transitions of the rotational quantum numbers
        acoordingly with the J and K selection rules. The arguments of this
        method must comes from another Rotational_Energies class, with the same
        arguments but potentially different values of A, B and C.

        Args:
            Jup (1darray): Values of the upper states of the J rotational number.
                This array must comes from <Rotational_Energies>.J
            Kup (1darray): Values of the upper states of the K rotational number.
            Eup (1darray): Values of the upper states of energy.
            Q_branch (bool, optional): Default to False. Wheter to consider
                or not the Q-branch.
        """
        df = pd.concat([self.J, self.K, self.E, self.population], axis=1)
        df.columns = ["J", "K", "E", "nJ"]
        df2 = pd.DataFrame({"J'": Jup, "K'": Kup, "E'": Eup})

        E_list, E_prime_list, J_list, J_prime_list = [], [], [], []
        K_list, K_prime_list, nJ_list = [], [], []

        if self.symmetry_type == 'spherical':

            # Selection rules (with or without Q-branch)
            if not Q_Branch:
                DeltaJ = [-1, 1]

            else:
                DeltaJ = [-1, 0, 1]
            # print("Starting search for allowed transitions")
            # For every initial state.
            for i in range(len(df.index)):

                # Get current values of Jup, Eup and Kup
                Jupp = df2["J'"].iloc[i]
                Eupp = df2["E'"].iloc[i]
                Kupp = df2["K'"].iloc[i]

                # Allowed transition values for Jup
                allowedJ = [Jupp-DelJ for DelJ in DeltaJ]

                # Get all the states that are allowed to transitionate to Jup
                # by the J selection rule
                df4 = pd.DataFrame(df.loc[df.J.isin(allowedJ)])

                # Add Jupp, Eupp and Kupp to DataFrame of allowed transitions.
                df4["J'"] = Jupp
                df4["E'"] = Eupp
                df4["K'"] = Kupp

                # Save results of iteration.
                E_list.extend(df4["E"].values)
                J_list.extend(df4["J"].values)
                nJ_list.extend(df4["nJ"].values)
                E_prime_list.extend(df4["E'"].values)
                J_prime_list.extend(df4["J'"].values)
                K_list.extend(df4["K"].values)
                K_prime_list.extend(df4["K'"].values)

        elif 'symmetric' in self.symmetry_type:
            # print("Starting search for allowed transitions")
            # For every initial state
            for i in range(len(df.index)):

                # Get current values of J, E and K.
                Jupp = df2["J'"].iloc[i]
                Eupp = df2["E'"].iloc[i]
                Kupp = df2["K'"].iloc[i]

                # Selection rules for K.
                DeltaK = [0]

                # Selection rules for J.
                if df["K"].iloc[i] == 0:
                    DeltaJ = [-1, 1]

                else:
                    DeltaJ = [-1, 0, 1]

                # Allowed transition values.
                allowedJ = [Jupp-DelJ for DelJ in DeltaJ]
                allowedK = [Kupp-DelK for DelK in DeltaK]

                # Final states that agree with the allowed transitions.
                df4 = pd.DataFrame(df.loc[df.J.isin(allowedJ) & df.K.isin(allowedK)])

                # Add values to DataFrame of allowed transitions.
                df4["J'"] = Jupp
                df4["E'"] = Eupp
                df4["K'"] = Kupp

                # Save results of iteration.
                E_list.extend(df4["E"].values)
                J_list.extend(df4["J"].values)
                nJ_list.extend(df4["nJ"].values)
                E_prime_list.extend(df4["E'"].values)
                J_prime_list.extend(df4["J'"].values)
                K_list.extend(df4["K"].values)
                K_prime_list.extend(df4["K'"].values)

        else:
            print('symmetry type not yet available')

        # Save allowed combinations in Class.
        df3 = pd.DataFrame({"E": E_list, "E'": E_prime_list, "J": J_list,
                            "J'": J_prime_list, "K": K_list,
                            "K'": K_prime_list, "nJ": nJ_list})
        self.allowed_combo_data = df3

    def transition_freq_and_pop(self):
        """Get the frequencie and population of transitions.

        Get the frequency of the allowed transitions and their itensities
        acoordingly with their population.
        """
        if self.allowed_combo_data is None:
            print("Do not have relevant data")

        else:
            # Compute frecuencies.
            self.transition_freqs = (self.allowed_combo_data["E'"] -
                                     self.allowed_combo_data["E"])

            # Change in the J rotational number.
            self.allowed_combo_data['DeltaJ'] = (self.allowed_combo_data["J'"]
                                                 - self.allowed_combo_data["J"])

            # Re-scale the PQR branches.
            self.allowed_combo_data['nJ'].loc[self.allowed_combo_data['DeltaJ'] == 0] = \
                self.allowed_combo_data["nJ"]*self.Q_scale
            self.allowed_combo_data['nJ'].loc[self.allowed_combo_data['DeltaJ'] != 0] = \
                self.allowed_combo_data["nJ"]*self.PR_scale

            # Intensity proportional to population.
            self.transition_intensity = self.allowed_combo_data["nJ"]

            # Find highest populated state.
            max_pop_idx = self.transition_intensity.astype('float64').idxmax()
            self.highest_pop_state = (self.allowed_combo_data["J"].iloc[max_pop_idx])

            # print("Jmax=" ,self.highest_pop_state)
            
            

    def plot_level_structure(self):
        J_low=self.allowed_combo_data["J"]*(self.allowed_combo_data["J"]+1)
        J_high=self.allowed_combo_data["J'"]*(self.allowed_combo_data["J'"]+1)
        freqs=self.transition_freqs
        
        
        fig, axs = plt.subplots(2,sharex=True)
        fig.suptitle('Plotting Level Structure: B='+str(self.B))
        axs[1].plot(freqs, J_low,'b.',marker='None')
        axs[0].plot(freqs, J_high,'b.',marker='None')
        axs[1].set_yticks(ticks=J_low)
        axs[0].set_yticks(ticks=J_high)
        
    
        for i in range(len(J_high)):
            xy_low = (freqs[i], J_low[i])
            xy_high = (freqs[i], J_high[i])
            con = ConnectionPatch(xyA=xy_low, xyB=xy_high, coordsA="data", coordsB="data", axesA=axs[1], axesB=axs[0], arrowstyle="-|>",color="blue")
            axs[1].add_artist(con)
        axs[1].grid(b=True,axis='y',which='major',c='grey',alpha=0.5)
        axs[0].grid(b=True,axis='y',which='major',c='grey',alpha=0.5)
        axs[1].set_ylabel(r"($\times$B): V")
        axs[0].set_ylabel(r"($\times$B): V'")
        plt.tick_params(labelbottom=False,bottom=False)
        
        
        

    def plot_transitions(self):
        """Plot the resulting transitions."""
        # print("Plotting the resulting transitions")

        # Plot every transition line (size equivalent to intensity).
        plt.vlines(x=self.transition_freqs, ymax=self.transition_intensity,
                   ymin=0, color='black', label='transitions')

        # DataFrame of transitions.
        df = pd.DataFrame({"Trans_Freqs": self.transition_freqs,
                           "Trans_Intens": self. transition_intensity,
                           "Delta J": self.allowed_combo_data["J'"] -
                           self.allowed_combo_data["J"]})

        # Transitions sorted by frequency.
        df = df.sort_values(by=["Trans_Freqs"])
        self.sorted_freqs = df["Trans_Freqs"]
        self.sorted_intens = df["Trans_Intens"]

        # Plot details.
        plt.xlabel("Transition Frequency (1/cm)")
        plt.ylabel("Intensity")
        plt.title(str(self.Target))
        plt.savefig(str(self.Target)+'_'+self.symmetry_type+".pdf")

    def _rebin_data(self, X, Y, bin_size, Verbose=False):
        """Resample data with a given interval.

        Args:
            X (1darray): Data of the X axis.
            Y (1darray): Data of the Y axis.
            bin_size (float): Interval for resampling.
            Verbose (bool, optional): Default to False. Wheter or not to
                describe progress of execution.

        Returns:
            rebinned_x (1darray): Resampled X data.
            rebinned_y (1darray): Resampled Y data.
        """
        rebinned_x, rebinned_y = [], []

        # Internvals to resample X data.
        bins = np.arange(float(np.min(X))-5,
                         float(np.max(X))+5, bin_size)

        # Classification of X data in bins.
        inds = np.digitize(X, bins)

        # DataFrame for saving results.
        df2 = pd.DataFrame({"X": X, "Y": Y, "bin": inds})

        # For every bin.
        for i in range(1, len(bins)):

            # Elements in the i-th bin.
            search = df2.loc[df2["bin"] == i]

            # If not empty.
            if len(search.index) != 0:

                # Center of bin.
                center_wave = bins[i]-bin_size/2

                # Intensity of bin.
                sum_y = search["Y"].sum()

                # Save results of iteration.
                rebinned_x.append(center_wave)
                rebinned_y.append(sum_y/bin_size)

                # Describe progress.
                if Verbose:
                    print('Bin:', i, 'from', bins[i-1], 'to', bins[i])
                    print('Wavenlength:', bins[i]-bin_size/2)
                    print(search)
                    print('Sum of Y:', sum_y)
                    print('Y To Plot:', sum_y/bin_size)
                    print('---------')

            # If empty, just assigne zero intensity to bin.
            else:
                center_wave = bins[i]-bin_size/2
                rebinned_x.append(center_wave)
                rebinned_y.append(0)

        # Return rebinned data.
        return(rebinned_x, rebinned_y)

    def _CreateWave(self, X, Y, lambda0):
        """Transform and resample data to final contour data.

        Args:
            X (1darray): X data array. Must have 1/cm units.
            Y (1darray): y data array.
            lambda0 (float): Center wavelength of DIB. (Angstrom)

        Returns:
            Final_X (1darray): Final transformed X data.
            Y_sampled (1darray): Final transformed Y data.
        """
        # Some constants.
        c = const.c.to('km/s')
        kms = (u.km / u.s)

        # convert X into velocity space.
        V = [((c*(del_sigma*u.k*lambda0*u.AA)).to(u.km / u.s)).value for del_sigma in X]

        # resample V and Y at 0.1km/s intervals
        bin_size = 0.1
        X_sampled, Y_sampled = self._rebin_data(V, Y, bin_size)

        # Convert velocities back into wavelengths
        Final_X = [((lambda0*u.AA*(1+(V*kms/c))).to(u.AA)).value for V in X_sampled]

        return(Final_X, Y_sampled)

    def apply_voigt(self, lambda0, show_figure=False):
        """Apply voigt profile to frequencies and intensities.

        Apply a voig profile (convolution of Cauchy-Lorentz and Gaussian
        distributions) to model the (frecuency, intensity) class data.

        Args:
            lambda0 (float): Center wavelenght of DIB. (Angstroms).
            show_figure (bool): Default to False. Wheter or not to show the
                resulting figure.
        """
        # Get data from class.
        X = self.transition_freqs
        Y = self.transition_intensity

        # Get wave from data.
        Wave, Intensity = self._CreateWave(X, Y, lambda0)

        # Array for final taus of voigt profile.
        final_tau = np.zeros(len(Wave))

        # For every data point.
        for i in range(len(Wave)):
            # Apply voigt optical depth.
            tau = voigt_optical_depth(Wave, lambda0=Wave[i], b=1, N=Intensity[i]*10**10,
                                      f=1, gamma=1e7, v_rad=0)
            final_tau = final_tau+tau

        # Save results in class.
        self.spectrax = Wave
        self.spectray = final_tau

        # Plot results.
        if show_figure:
            plt.plot(Wave, final_tau, 'k-', label='voigt profile applied')
            plt.xlabel('Wavelength $\mathrm{\AA}$')
            plt.ylabel('Tau')
            plt.show()

    def apply_radiative_transfer(self, show_figure=False):
        """Apply radiative transfer to data from voigt profile.

        Args:
            show_figure (bool, optional): Defalut is False. Wheter or not to show the
                resulting figure.
        """
        self.simple_rt_y = 1-self.spectray
        self.full_rt_y = np.exp(-self.spectray)

        # Plot results.
        if show_figure:
            plt.plot(self.spectrax, self.simple_rt_y, 'k-',
                     label='after radiative transfer step')

            plt.xlabel('Wavelength $\mathrm{\AA}$')
            plt.ylabel('Optical Depth')
            plt.show()
        return()

    def smooth_spectra(self, lambda0, show_figure=False):
        """Smooth spectra.

        Smooth spectra via a 1D Gaussian Kernel.

        Args:
            lambda0  (float): Center wavelenght of DIB. (Angstroms).
            show_figure (bool, optional): Defalut is False. Wheter or not to show the
                resulting figure.
        """
        dx = np.asarray(self.spectrax[1:])-np.asarray(self.spectrax[0:-1])
        d_lambda = lambda0/80000
        sigma_a = d_lambda/2.355
        sigma_p = sigma_a/dx[0]

        # Smooth data through a 1d Gaussian kernel.
        kernal = Gaussian1DKernel(sigma_p)
        convolved_y = convolve(self.full_rt_y, kernal, boundary='extend')

        # Plot results.
        if show_figure:
            plt.plot(self.spectrax, convolved_y/np.max(convolved_y),
                     'c-', label='after smoothing')
            plt.xlabel('Wavelength $\mathrm{\AA}$')
            plt.ylabel('Normalized Intensity')

        # Save results in class.
        self.final_y = convolved_y/np.max(convolved_y)

        return()

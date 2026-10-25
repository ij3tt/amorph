# Uses actual DNest4 stuff if it's installed - otherwise
# uses dnest_functions.py as a fallback
try:
    import dnest4.classic as dn4
except ImportError:
    import dnest_functions as dn4

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import yaml

import amorph_stats

def display():
    """
    Function to load and plot the output of a run.
    """
    f = open("config.yaml")
    config = yaml.load(f, Loader=yaml.SafeLoader)
    f.close()

    # Load the data file, with the same rules as the sampler
    x, y = amorph_stats.load_data(config["data_file"])

    # Load posterior samples etc
    posterior_sample = dn4.my_loadtxt("posterior_sample.txt")
    temp = dn4.load_column_names("posterior_sample.txt")
    indices = temp["indices"]

    # The curves of all the posterior samples, one row per sample
    def curves(first):
        start = indices[first]
        return posterior_sample[:, start:start + x.size]

    bg = curves("bg[0]")
    wide_component = curves("wide[0]")
    the_spikes = curves("narrow[0]")
    model = curves("model_curve[0]")

    max_num_spikes = int(posterior_sample[0, indices["max_num_peaks1"]])
    num_spikes = posterior_sample[:, indices["num_peaks1"]]

    # A data frame to store some results
    macroquantities = pd.DataFrame()

    # Plot the model. 50 posterior samples and the
    # posterior mean for each part.
    plt.clf()
    for i in range(0, min(posterior_sample.shape[0], 50)):
        plt.plot(x, model[i, :], "g", linewidth=1, alpha=0.1)
        plt.plot(x, wide_component[i, :], "b", linewidth=1, alpha=0.1)
        plt.plot(x, the_spikes[i, :], "r", linewidth=1, alpha=0.1)
        plt.plot(x, bg[i, :], "y", linewidth=1, alpha=0.1)
        plt.ylim(0)

    # Plot the posterior means
    plt.plot(x, model.mean(axis=0), "g-", linewidth=3, alpha=1)
    plt.plot(x, wide_component.mean(axis=0), "b--", linewidth=3, alpha=1)
    plt.plot(x, the_spikes.mean(axis=0), "r--", linewidth=3, alpha=1)
    plt.plot(x, bg.mean(axis=0), "y--", linewidth=3, alpha=1)

    # Plot the data
    plt.plot(x, y, "ko", markersize=3, alpha=0.5)
    plt.xlabel("$2\\theta$ (degrees)", fontsize=14)
    plt.ylabel("Intensity", fontsize=14)
    plt.show()

    # Plot the standardised residuals of the posterior mean curve.
    # Use the posterior mean of sigma0 and sigma1 for the standardisation.
    # This is not ideal - really there is a posterior distribution over
    # residuals.
    curve = model.mean(axis=0)
    sd = np.sqrt(posterior_sample[:,indices["sigma0"]].mean()**2 \
                    + posterior_sample[:,indices["sigma1"]].mean()*curve)
    resid = (curve - y)/sd
    plt.plot(x, resid, "-")
    plt.xlabel("$2\\theta$ (degrees)")
    plt.ylabel("Standardised residuals (of posterior mean model curve)")
    plt.show()

    # Number of narrow components: one bin per count from 0 to the maximum
    plt.hist(num_spikes, bins=np.arange(0, max_num_spikes + 2) - 0.5,
             rwidth=0.8, color=[0.3, 0.3, 0.3])
    plt.xlabel("Number of narrow components")
    plt.ylabel("Number of posterior samples")

    # A data frame to store some results
    macroquantities["num_narrow_peaks"] = num_spikes
    plt.show()

    # A sample without a wide component counts as 0% amorphous
    wide_fraction = amorph_stats.amorphous_fraction(wide_component,
                                                    the_spikes, x)
    macroquantities["amorph/(amorph + crystal)"] = wide_fraction

    # Remove any nans before plotting
    wide_fraction = wide_fraction[~np.isnan(wide_fraction)]

    plt.hist(wide_fraction, 100, color=[0.3, 0.3, 0.3])
    plt.xlim([0, 1])
    plt.xlabel("(amorph)/(amorph + crystal)")
    print("(amorph)/(amorph + crystal) = {a} +- {b}".format(a=wide_fraction.mean(),\
           b=wide_fraction.std()))
    plt.show()

    # The shape of the wide component: NaN for samples without one
    wide_center_of_mass, wide_width, wide_skewness, wide_nongaussianity = \
                    amorph_stats.wide_component_shape(x, wide_component)

    macroquantities["wide_center_of_mass"] = wide_center_of_mass

    wide_center_of_mass = wide_center_of_mass[~np.isnan(wide_center_of_mass)]
    plt.hist(wide_center_of_mass, 100, color=[0.3, 0.3, 0.3])
    plt.xlabel("Center of mass of wide component")
    print("Center of mass = {a} +- {b}".format(a=wide_center_of_mass.mean(),
           b=wide_center_of_mass.std()))
    plt.show()

    macroquantities["wide_halfwidth"] = wide_width
    wide_width = wide_width[~np.isnan(wide_width)]
    plt.hist(wide_width, 100, color=[0.3, 0.3, 0.3])
    plt.xlabel("Half-width of wide component")
    print("Half-width = {a} +- {b}".format(a=wide_width.mean(),
           b=wide_width.std()))
    plt.show()

    macroquantities["wide_skewness"] = wide_skewness
    wide_skewness = wide_skewness[~np.isnan(wide_skewness)]
    plt.hist(wide_skewness, 100, color=[0.3, 0.3, 0.3])
    plt.xlabel("Skewness of wide component")
    print("Skewness = {a} +- {b}".format(a=wide_skewness.mean(),
           b=wide_skewness.std()))
    plt.show()

    macroquantities["wide_nongaussianity"] = wide_nongaussianity
    wide_nongaussianity = wide_nongaussianity[~np.isnan(wide_nongaussianity)]
    plt.hist(wide_nongaussianity, 100, color=[0.3, 0.3, 0.3])
    plt.xlabel("Nongaussianity of wide component")
    plt.xlim(0.0)
    print("Nongaussianity = {a} +- {b}".format(a=wide_nongaussianity.mean(),
           b=wide_nongaussianity.std()))
    plt.show()

    print("Saving macroquantities.csv")
    macroquantities.index = range(1, posterior_sample.shape[0]+1)
    macroquantities.to_csv("macroquantities.csv",
                           index_label="Sample number")

if __name__ == "__main__":
    display()


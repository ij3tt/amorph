#ifndef AMORPH_MyModel_h
#define AMORPH_MyModel_h

#include <ostream>
#include <string>
#include <tuple>
#include "DNest4/code/DNest4.h"
#include "Data.h"
#include "MyConditionalPrior.h"

namespace AMORPH
{

class MyModel
{
    private:
        // Constant background
        double background;

        // Knots in background
        std::vector<double> n_knots;

        // Use an RJObject for the narrow spikes and one for the wide spikes
        DNest4::RJObject<MyConditionalPrior> narrow_peaks, wide_peaks;

        // Shape parameter of narrow peaks
        double peak_shape;

        // Noise-related parameters
        double sigma0, sigma1, nu;

        // Components of the model-predicted curve
        std::vector<double> bg;
        std::vector<double> narrow;
        std::vector<double> wide;

        // Number of updates of the narrow and wide curves since they were
        // last computed in full
        int narrow_updates, wide_updates;

        // Calculate the parts of the model-predicted curve. An update of the
        // curve of the peaks subtracts the peaks that the last perturbation
        // removed and adds those it added.
        void compute_bg();
        void compute_narrow(bool update=false);
        void compute_wide(bool update=false);
        void compute_peaks(const DNest4::RJObject<MyConditionalPrior>& peaks,
                           double shape, bool update,
                           std::vector<double>& curve, int& num_updates);

    public:
        // Constructor only gives size of params
        MyModel();

        // Generate the point from the prior
        void from_prior(DNest4::RNG& rng);

        // Metropolis-Hastings proposals
        double perturb(DNest4::RNG& rng);

        // Likelihood function
        double log_likelihood() const;

        // Print to stream
        void print(std::ostream& out) const;

        // Return string with column information
        std::string description() const;

        // For the tests: the curves of the narrow and wide peaks, and a
        // computation of all the curves from scratch
        const std::vector<double>& get_narrow() const { return narrow; }
        const std::vector<double>& get_wide() const { return wide; }
        void recompute_curves();


        /********** STATIC STUFF **********/
    private:
        // The dataset!
        static Data data;

        // A useful laplace distribution
        static const DNest4::Laplace laplace;

        // x-positions of background knots
        static std::vector<double> x_knots;

        // The largest |y| of the data
        static double y_scale;

        // The curves of the peaks are computed in full after this many
        // updates, so that rounding errors cannot build up
        static const int max_num_updates = 1000;

    public:
        static void load_data(const char* filename);
        static void set_control_points(const std::tuple<double, double>& cps);
        static const std::vector<double>& get_x_knots() { return x_knots; }

        // A warning if the control points lie outside the range of the data,
        // or an empty string if they do not. Call it after load_data().
        static std::string control_points_warning();
};

} // namespace AMORPH

#endif


#include "MyModel.h"
#include "Background.h"
#include "Config.h"
#include "DNest4/code/DNest4.h"
#include "Likelihood.h"
#include "Peaks.h"
#include <algorithm>
#include <cmath>
#include <sstream>
#include <stdexcept>

namespace AMORPH
{

// Static things
Data MyModel::data;
const DNest4::Laplace MyModel::laplace(0.0, 20.0);
// The outer background knots are the edges of the data, set by load_data():
// they cannot be read from the data here, before they are loaded.
std::vector<double> MyModel::x_knots{0.0, 10.0, 40.0, 0.0};
double MyModel::y_scale = 0.0;

// Constructor
MyModel::MyModel()
:n_knots(4)
,narrow_peaks(3, Config::global.get_max_num_narrow_peaks(), false,
            MyConditionalPrior(data.get_x_min(), data.get_x_max(), true),
                                DNest4::PriorType::log_uniform)
,wide_peaks(3, Config::global.get_max_num_wide_peaks(), false,
            MyConditionalPrior(data.get_x_min(), data.get_x_max(), false),
                                DNest4::PriorType::log_uniform)
,bg(data.get_y().size())
,narrow(data.get_y().size())
,wide(data.get_y().size())
,narrow_updates(0)
,wide_updates(0)
{
    if(!data.get_loaded())
        std::cerr<<"# WARNING: it appears no data has been loaded."<<std::endl;
}

void MyModel::from_prior(DNest4::RNG& rng)
{
    background = exp(laplace.generate(rng));
    for(double& nn: n_knots)
        nn = rng.randn();

    narrow_peaks.from_prior(rng);
    wide_peaks.from_prior(rng);

    // log(nu) of the narrow peaks, uniform between the bounds in the config
    double shape_min = log(Config::global.get_narrow_peak_nu_min());
    double shape_max = log(Config::global.get_narrow_peak_nu_max());
    peak_shape = shape_min + (shape_max - shape_min)*rng.rand();

    compute_bg();
    compute_narrow();
    compute_wide();

    sigma0 = exp(laplace.generate(rng));
    sigma1 = exp(laplace.generate(rng));
    nu = exp(log(1.0) + log(1E3)*rng.rand());
}

double MyModel::perturb(DNest4::RNG& rng)
{
    double logH = 0.0;

    // Select blocks of parameters
    int choice = rng.rand_int(3);

    if(choice == 0)
    {
        // Perturb spikes
        logH += narrow_peaks.perturb(rng);

        // Save computational time by handling prior-based rejection here
        if(rng.rand() >= exp(logH))
            return -1E300;
        else
            logH = 0.0;

        compute_narrow(true);
    }
    else if(choice == 1)
    {
        // Perturb spikes
        logH += wide_peaks.perturb(rng);

        // Save computational time by handling prior-based rejection here
        if(rng.rand() >= exp(logH))
            return -1E300;
        else
            logH = 0.0;

        compute_wide(true);
    }
    else
    {
        // Perturb one of these parameters
        int which = rng.rand_int(6);

        if(which == 0)
        {
            background = log(background);
            logH += laplace.perturb(background, rng);
            background = exp(background);

            compute_bg();
        }
        else if(which == 1)
        {
            int i = rng.rand_int(n_knots.size());
            logH -= -0.5*pow(n_knots[i], 2);
            n_knots[i] += rng.randh();
            logH += -0.5*pow(n_knots[i], 2);

            compute_bg();
        }
        else if(which == 2)
        {
            double shape_min = log(Config::global.get_narrow_peak_nu_min());
            double shape_max = log(Config::global.get_narrow_peak_nu_max());
            peak_shape += (shape_max - shape_min)*rng.randh();
            DNest4::wrap(peak_shape, shape_min, shape_max);

            compute_narrow();
        }
        else if(which == 3)
        {
            sigma0 = log(sigma0);
            logH += laplace.perturb(sigma0, rng);
            sigma0 = exp(sigma0);
        }
        else if(which == 4)
        {
            sigma1 = log(sigma1);
            logH += laplace.perturb(sigma1, rng);
            sigma1 = exp(sigma1);
        }
        else
        {
            nu = log(nu);
            nu += log(1E3)*rng.randh();
            DNest4::wrap(nu, log(1.0), log(1E3));
            nu = exp(nu);
        }
    }

    return logH;
}

void MyModel::compute_bg()
{
    // Background level at the knots
    std::vector<double> y_knots(n_knots.size());
    for(size_t i=0; i<n_knots.size(); ++i)
        y_knots[i] = background * exp(n_knots[i]);

    const auto& data_x = data.get_x();
    for(size_t i=0; i<bg.size(); ++i)
        bg[i] = piecewise_linear(x_knots, y_knots, data_x[i]);
}


void MyModel::compute_narrow(bool update)
{
    compute_peaks(narrow_peaks, peak_shape, update, narrow, narrow_updates);
}

void MyModel::compute_wide(bool update)
{
    compute_peaks(wide_peaks, log(100.0), update, wide, wide_updates);
}

void MyModel::compute_peaks(const DNest4::RJObject<MyConditionalPrior>& peaks,
                            double shape, bool update,
                            std::vector<double>& curve, int& num_updates)
{
    const auto& data_x = data.get_x();
    const auto& components = peaks.get_components();
    const auto& added = peaks.get_added();
    const auto& removed = peaks.get_removed();

    if(update && added.empty() && removed.empty())
        return;

    // Compute the curve in full when asked to, after max_num_updates
    // updates, or when an update would evaluate as many peaks. The last
    // includes having no peaks left, so that the curve is then exactly zero.
    bool full = !update || num_updates >= max_num_updates
                    || added.size() + removed.size() >= components.size();

    // Subtracting a peak leaves rounding errors of about 1E-16 times its
    // height (mass/width) for each update made while it was there. That
    // only matters for a peak far taller than the data, as the sampler can
    // propose while it explores the prior: such a peak is not subtracted.
    for(size_t i=0; i<removed.size() && !full; ++i)
        full = exp(removed[i][1])/removed[i][2] > 1E3*y_scale;

    if(full)
    {
        std::fill(curve.begin(), curve.end(), 0.0);
        add_peaks(components, shape, 1.0, data_x, curve);
        num_updates = 0;
    }
    else
    {
        add_peaks(removed, shape, -1.0, data_x, curve);
        add_peaks(added, shape, 1.0, data_x, curve);
        ++num_updates;
    }
}

void MyModel::recompute_curves()
{
    compute_bg();
    compute_narrow();
    compute_wide();
}

double MyModel::log_likelihood() const
{
    // T likelihood
    auto model = [this](size_t i) { return bg[i] + narrow[i] + wide[i]; };
    double logL = student_t_log_likelihood(data.get_y(), model, sigma0,
                                           sigma1, nu);

    if(std::isnan(logL) || std::isinf(logL))
        logL = -1E300;

    return logL;
}

void MyModel::set_control_points(const std::tuple<double, double>& cps)
{
    if(std::get<0>(cps) >= std::get<1>(cps))
        throw std::invalid_argument("The background control points must be "
                                    "in increasing order.");

    std::tie(x_knots[1], x_knots[2]) = cps;
}

void MyModel::print(std::ostream& out) const
{
    out<<background<<' ';
    for(double nn: n_knots)
        out<<nn<<' ';

    narrow_peaks.print(out);
    wide_peaks.print(out);
    out<<peak_shape<<' ';
    out<<sigma0<<' '<<sigma1<<' '<<nu<<' ';

    for(size_t i=0; i<bg.size(); ++i)
        out<<bg[i]<<' ';

    for(size_t i=0; i<narrow.size(); ++i)
        out<<narrow[i]<<' ';

    for(size_t i=0; i<wide.size(); ++i)
        out<<wide[i]<<' ';

    double model;
    for(size_t i=0; i<wide.size(); ++i)
    {
        model = bg[i] + narrow[i] + wide[i];
        out<<model<<' ';
    }
}

std::string MyModel::description() const
{
    std::stringstream s;
    s<<"background, ";
    for(size_t i=0; i<n_knots.size(); ++i)
        s<<"n_knots["<<i<<"], ";

    s<<"dim_peaks1, max_num_peaks1, ";
    s<<"location_log_amplitude1, scale_log_amplitude1, ";
    s<<"location_log_width1, scale_log_width1, num_peaks1, ";
    for(size_t i=0; i<Config::global.get_max_num_narrow_peaks(); ++i)
        s<<"center1["<<i<<"], ";
    for(size_t i=0; i<Config::global.get_max_num_narrow_peaks(); ++i)
        s<<"log_amplitude1["<<i<<"], ";
    for(size_t i=0; i<Config::global.get_max_num_narrow_peaks(); ++i)
        s<<"width1["<<i<<"], ";

    s<<"dim_peaks2, max_num_peaks2, ";
    s<<"location_log_amplitude2, scale_log_amplitude2, ";
    s<<"location_log_width2, scale_log_width2, num_peaks2, ";
    for(size_t i=0; i<Config::global.get_max_num_wide_peaks(); ++i)
        s<<"center2["<<i<<"], ";
    for(size_t i=0; i<Config::global.get_max_num_wide_peaks(); ++i)
        s<<"log_amplitude2["<<i<<"], ";
    for(size_t i=0; i<Config::global.get_max_num_wide_peaks(); ++i)
        s<<"width2["<<i<<"], ";

    s<<"peak_shape, ";
    s<<"sigma0, sigma1, nu, ";

    for(size_t i=0; i<narrow.size(); ++i)
        s<<"bg["<<i<<"], ";
    for(size_t i=0; i<narrow.size(); ++i)
        s<<"narrow["<<i<<"], ";
    for(size_t i=0; i<wide.size(); ++i)
        s<<"wide["<<i<<"], ";
    for(size_t i=0; i<wide.size(); ++i)
        s<<"model_curve["<<i<<"], ";

    return s.str();
}

void MyModel::load_data(const char* filename)
{
    data.load(filename);

    x_knots[0] = data.get_x_min();
    x_knots[3] = data.get_x_max();

    y_scale = 0.0;
    for(double y: data.get_y())
        y_scale = std::max(y_scale, std::abs(y));
}

std::string MyModel::control_points_warning()
{
    // The knots are x_min, the two control points and x_max. A control
    // point on the edge of the data is fine.
    if(x_knots[1] >= x_knots[0] && x_knots[2] <= x_knots[3])
        return "";

    std::stringstream s;
    s<<"the background control points ("<<x_knots[1]<<", "<<x_knots[2]
     <<") lie outside the range of the data ("<<x_knots[0]<<" to "
     <<x_knots[3]<<"). Check control_points in config.yaml.";
    return s.str();
}

} // namespace AMORPH


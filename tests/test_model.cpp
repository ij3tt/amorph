/*
* Unit tests of the parts of the AMORPH model that can be checked without
* running the sampler. Run by ctest: the exit status is 1 if any check fails.
*/

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <limits>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

#include "Background.h"
#include "Config.h"
#include "DNest4/code/DNest4.h"
#include "Likelihood.h"
#include "Lookup.h"
#include "MyModel.h"
#include "Peaks.h"

using namespace AMORPH;

static constexpr double pi = 3.141592653589793;

static int num_failed = 0;

// Report a check without stopping, so that one run shows all the failures
static void check(bool ok, const std::string& what)
{
    std::cout<<(ok?"ok      ":"FAILED  ")<<what<<std::endl;
    if(!ok)
        ++num_failed;
}

static bool is_close(double a, double b, double tol)
{
    return std::abs(a - b) <= tol*std::max(1.0, std::abs(b));
}

static std::string str(double x)
{
    std::stringstream ss;
    ss<<x;
    return ss.str();
}

static std::string str(const std::vector<double>& v)
{
    std::stringstream ss;
    for(size_t i=0; i<v.size(); ++i)
        ss<<((i == 0)?"":" ")<<v[i];
    return ss.str();
}

/***************************** Likelihood *****************************/

// Integral of r^power times the t density over the real line. With
// r = sqrt(var)*tan(theta) it becomes an integral over (-pi/2, pi/2) with a
// smooth integrand, done with the midpoint rule.
static double t_moment(double var, double nu, int power)
{
    const int n = 200000;
    const double h = pi/n;
    const double s = std::sqrt(var);

    double total = 0.0;
    for(int i=0; i<n; ++i)
    {
        double theta = -0.5*pi + (i + 0.5)*h;
        double r = s*std::tan(theta);
        double dr_dtheta = s/std::pow(std::cos(theta), 2);
        total += std::pow(r, power)*std::exp(student_t_log_pdf(r, var, nu))
                    *dr_dtheta;
    }
    return total*h;
}

static void test_student_t()
{
    // The density is normalised, for any nu and var
    for(double nu: {1.0, 2.0, 5.0, 30.0, 1000.0})
        for(double var: {0.01, 1.0, 400.0})
        {
            double integral = t_moment(var, nu, 0);
            check(is_close(integral, 1.0, 1E-6),
                  "t density integrates to 1 (nu=" + str(nu) + ", var="
                  + str(var) + "): " + str(integral));
        }

    // sqrt(var) is the scale of the distribution, as in the paper, so the
    // variance of the residuals is var*nu/(nu - 2)
    for(double nu: {3.0, 5.0, 30.0})
    {
        double variance = t_moment(2.0, nu, 2);
        check(is_close(variance, 2.0*nu/(nu - 2.0), 1E-5),
              "variance of the t density is var*nu/(nu - 2) (nu=" + str(nu)
              + ", var=2): " + str(variance));
    }

    // For large nu it is the normal distribution with variance var
    for(double r: {0.0, 1.0, 3.0})
    {
        double normal = -0.5*std::log(2.0*pi*2.0) - 0.5*r*r/2.0;
        double t = student_t_log_pdf(r, 2.0, 1E5);
        check(is_close(t, normal, 1E-3),
              "t density tends to the normal density (r=" + str(r) + "): "
              + str(t) + " vs " + str(normal));
    }
}

/***************************** Background *****************************/

static void test_piecewise_linear()
{
    std::vector<double> x_knots{5.0, 10.0, 40.0, 50.0};
    std::vector<double> y_knots{1.0, 2.0, 3.0, 4.0};

    for(size_t i=0; i<x_knots.size(); ++i)
    {
        double y = piecewise_linear(x_knots, y_knots, x_knots[i]);
        check(is_close(y, y_knots[i], 1E-12),
              "background passes through knot " + str(x_knots[i]) + ": "
              + str(y));
    }
    double y = piecewise_linear(x_knots, y_knots, 25.0);
    check(is_close(y, 2.5, 1E-12),
          "background is linear between the knots: " + str(y));

    // Data that only covers the range between the control points, like
    // "50% glass .02step3secdwell.txt" (10-40 degrees): the outer segments
    // have no length.
    x_knots = {10.0, 10.0, 40.0, 40.0};
    for(double x: {10.0, 25.0, 40.0})
    {
        y = piecewise_linear(x_knots, y_knots, x);
        check(std::isfinite(y) && is_close(y, 2.0 + (x - 10.0)/30.0, 1E-12),
              "background with zero-length outer segments at x=" + str(x)
              + ": " + str(y));
    }
}

static void test_background_knots()
{
    // A small dataset from 5 to 50 degrees
    const char* filename = "test_knots_data.txt";
    {
        std::fstream fout(filename, std::ios::out);
        for(int i=0; i<=45; ++i)
            fout<<(5.0 + i)<<' '<<100.0<<'\n';
    }

    // The order of main(): control points first, then the data
    MyModel::set_control_points(std::make_tuple(12.0, 38.0));
    MyModel::load_data(filename);
    std::vector<double> expected{5.0, 12.0, 38.0, 50.0};
    check(MyModel::get_x_knots() == expected,
          "background knots are x_min, the control points and x_max: "
          + str(MyModel::get_x_knots()));

    // The other way around
    MyModel::set_control_points(std::make_tuple(10.0, 40.0));
    expected = {5.0, 10.0, 40.0, 50.0};
    check(MyModel::get_x_knots() == expected,
          "control points set after loading the data: "
          + str(MyModel::get_x_knots()));

    bool threw = false;
    try
    {
        MyModel::set_control_points(std::make_tuple(40.0, 10.0));
    }
    catch(const std::invalid_argument&)
    {
        threw = true;
    }
    check(threw, "control points in the wrong order are rejected");

    std::remove(filename);
}

/******************************* Lookup *******************************/

static void test_lookup()
{
    // Every peak shape is normalised over the range of the table, [-20, 20]
    for(double nu: {0.1, 1.0, 10.0, 100.0})
    {
        const int n = 400000;
        const double h = 40.0/n;
        double total = 0.0;
        for(int i=0; i<n; ++i)
            total += Lookup::evaluate(std::log(nu), -20.0 + (i + 0.5)*h);
        total *= h;
        check(is_close(total, 1.0, 1E-3),
              "peak shape is normalised (nu=" + str(nu) + "): " + str(total));
    }
}

/******************************** Peaks ********************************/

// The curve of the peaks as the model computed it before the windows: every
// point of the grid is tested
static std::vector<double> peaks_full_loop(
                            const std::vector<std::vector<double>>& peaks,
                            double shape, const std::vector<double>& x)
{
    std::vector<double> y(x.size(), 0.0);
    double c, m, w, w_inv, coeff, xx;
    for(size_t i=0; i<peaks.size(); ++i)
    {
        c = peaks[i][0];
        m = std::exp(peaks[i][1]);
        w = peaks[i][2];
        w_inv = 1.0/w;
        coeff = m*w_inv;

        for(size_t j=0; j<y.size(); ++j)
        {
            xx = (x[j] - c)*w_inv;
            if(std::abs(xx) <= 20.0)
                y[j] += coeff*Lookup::evaluate(shape, xx);
        }
    }
    return y;
}

// Whether the window of each peak holds exactly the points within 20 widths
static bool windows_are_exact(const std::vector<std::vector<double>>& peaks,
                              const std::vector<double>& x)
{
    for(const auto& peak: peaks)
    {
        double w_inv = 1.0/peak[2];
        auto window = peak_window(x, peak[0], w_inv);
        for(size_t j=0; j<x.size(); ++j)
        {
            bool inside = std::abs((x[j] - peak[0])*w_inv) <= 20.0;
            if(inside != (j >= window.first && j < window.second))
                return false;
        }
    }
    return true;
}

static void test_peaks_windowed()
{
    std::mt19937_64 rng(42);
    std::uniform_real_distribution<double> u(0.0, 1.0);

    // A uniform grid like that of the bundled data, and an irregular one
    std::vector<std::vector<double>> grids(2);
    for(int j=0; j<1731; ++j)
        grids[0].push_back(5.0 + 0.026*j);
    double xj = 10.0;
    for(int j=0; j<500; ++j)
    {
        grids[1].push_back(xj);
        xj += 0.001 + 0.2*std::pow(u(rng), 3);
    }

    for(size_t g=0; g<grids.size(); ++g)
    {
        const auto& x = grids[g];
        double range = x.back() - x.front();

        bool same = true, exact_windows = true;
        for(int trial=0; trial<200; ++trial)
        {
            // Centres within and beyond the grid, some on a grid point, and
            // widths from far below the grid spacing to the whole range
            std::vector<std::vector<double>> peaks;
            int num_peaks = 1 + static_cast<int>(50*u(rng));
            for(int k=0; k<num_peaks; ++k)
            {
                double c = x.front() - 0.2*range + 1.4*range*u(rng);
                if(u(rng) < 0.2)
                    c = x[static_cast<size_t>(u(rng)*x.size())];
                double w = range*std::exp(std::log(1E-6)*u(rng));
                peaks.push_back({c, -5.0 + 10.0*u(rng), w});
            }
            // Also shapes beyond the table, which is for nu in [0.1, 100]
            double shape = std::log(0.05) + std::log(4000.0)*u(rng);

            std::vector<double> y(x.size(), 0.0);
            add_peaks(peaks, shape, 1.0, x, y);
            same = same && (y == peaks_full_loop(peaks, shape, x));
            exact_windows = exact_windows && windows_are_exact(peaks, x);
        }
        std::string grid = (g == 0)?"uniform grid":"irregular grid";
        check(same, "windowed peaks equal the loop over all the points "
                    "exactly (" + grid + ")");
        check(exact_windows, "the window of a peak holds the points within "
                             "20 widths (" + grid + ")");
    }

    // The points exactly 20 widths from the centre are in the window
    std::vector<double> x;
    for(int j=0; j<=60; ++j)
        x.push_back(0.5*j);
    auto window = peak_window(x, 15.0, 2.0);
    check(window.first == 10 && window.second == 51,
          "window of a peak at 15 of width 0.5 on 0, 0.5, ..., 30 is [10, "
          "51): [" + str(window.first) + ", " + str(window.second) + ")");

    // A peak of zero width has no points, not even its centre, where
    // (x - c)/width is NaN
    std::vector<std::vector<double>> peaks{{10.0, 0.0, 0.0}};
    window = peak_window(x, 10.0, 1.0/peaks[0][2]);
    std::vector<double> y(x.size(), 0.0);
    add_peaks(peaks, std::log(2.0), 1.0, x, y);
    check(window.first == window.second
            && y == peaks_full_loop(peaks, std::log(2.0), x),
          "a peak of zero width has an empty window");

    // Subtracting peaks takes away what adding them added, and leaves no
    // negative values
    std::vector<std::vector<double>> some{{12.0, 3.0, 0.3}, {20.0, 1.0, 2.0}};
    std::vector<std::vector<double>> more{{11.0, 8.0, 0.1}, {21.0, 2.0, 1.0}};
    y.assign(x.size(), 0.0);
    add_peaks(some, std::log(3.0), 1.0, x, y);
    add_peaks(more, std::log(3.0), 1.0, x, y);
    add_peaks(more, std::log(3.0), -1.0, x, y);
    std::vector<double> expected = peaks_full_loop(some, std::log(3.0), x);
    double error = 0.0, scale = 0.0, lowest = 0.0;
    for(size_t j=0; j<x.size(); ++j)
    {
        error = std::max(error, std::abs(y[j] - expected[j]));
        scale = std::max(scale, std::abs(expected[j]));
        lowest = std::min(lowest, y[j]);
    }
    check(error <= 1E-12*scale && lowest == 0.0,
          "subtracting peaks takes away what adding them added: error "
          + str(error/scale) + ", lowest value " + str(lowest));
}

/************************ Updates of the curves ************************/

// The largest difference between a curve and the same curve computed from
// scratch, relative to the largest value of the latter or to that of the
// data (y_max), whichever is larger. The curve enters the likelihood beside
// the data, so the scale of the data is the one that matters: while the
// sampler explores the prior, a curve can be nearly empty, and the rounding
// left by subtracting a tall peak is then large next to it but not next to
// the data. (The random numbers differ between C++ libraries, so the chain
// below reaches such states on some systems and not on others.)
static double curve_error(const std::vector<double>& y,
                          const std::vector<double>& full, double y_max)
{
    double error = 0.0, scale = y_max;
    for(size_t i=0; i<y.size(); ++i)
    {
        error = std::max(error, std::abs(y[i] - full[i]));
        scale = std::max(scale, std::abs(full[i]));
    }
    if(error == 0.0)
        return 0.0;
    return (scale > 0.0)?(error/scale):std::numeric_limits<double>::infinity();
}

static void test_curve_updates()
{
    // A dataset like an XRD pattern: background, a hump and a few peaks
    const char* data_file = "test_model_data.txt";
    const char* options_file = "test_model_options.txt";
    const char* config_file = "test_model_config.yaml";
    double y_max = 0.0;
    {
        std::fstream fout(data_file, std::ios::out);
        fout.precision(12);
        for(int i=0; i<=400; ++i)
        {
            double x = 10.0 + 0.15*i;
            double y = 50.0 + 200.0*std::exp(-0.5*std::pow((x - 30.0)/6.0, 2));
            for(double c: {22.0, 35.0, 51.0})
                y += 1000.0*std::exp(-0.5*std::pow((x - c)/0.2, 2));
            fout<<x<<' '<<y<<'\n';
            y_max = std::max(y_max, y);
        }
        std::fstream(options_file, std::ios::out)<<"# DNest4 options\n";
        std::fstream(config_file, std::ios::out)
            <<"num_threads: 1\n"
            <<"data_file: \""<<data_file<<"\"\n"
            <<"dnest4_options_file: \""<<options_file<<"\"\n"
            <<"inference_assumptions:\n"
            <<"    control_points: [20.0, 60.0]\n"
            <<"    max_num_narrow_peaks: 200\n"
            <<"    max_num_wide_peaks: 30\n"
            <<"    left_edge: 0.3\n"
            <<"    right_edge: 0.7\n";
    }
    Config::global.load(config_file);
    MyModel::set_control_points(Config::global.get_control_points());
    MyModel::load_data(data_file);

    // A chain that samples the prior, as DNest4 does before it has made
    // any levels: the peaks are born, die and move, nu changes, and every
    // peak moves when the hyperparameters do
    DNest4::RNG rng(1);
    MyModel model;
    model.from_prior(rng);

    const int num_steps = 30000;
    double narrow_error = 0.0, wide_error = 0.0;
    int num_updated = 0;
    for(int i=0; i<num_steps; ++i)
    {
        MyModel proposal = model;
        double log_H = proposal.perturb(rng);
        if(rng.rand() <= std::exp(std::min(log_H, 0.0)))
            model = proposal;

        MyModel full = model;
        full.recompute_curves();
        narrow_error = std::max(narrow_error,
                                curve_error(model.get_narrow(),
                                            full.get_narrow(), y_max));
        wide_error = std::max(wide_error,
                              curve_error(model.get_wide(), full.get_wide(),
                                          y_max));
        if(model.get_narrow() != full.get_narrow()
                || model.get_wide() != full.get_wide())
            ++num_updated;
    }

    check(narrow_error <= 1E-9,
          "updated curve of the narrow peaks equals a full computation, "
          "over " + str(num_steps) + " steps: largest relative error "
          + str(narrow_error));
    check(wide_error <= 1E-9,
          "updated curve of the wide peaks equals a full computation: "
          "largest relative error " + str(wide_error));
    check(num_updated > 0,
          "the curves were updated rather than computed in full (they "
          "differed from a full computation in " + str(num_updated)
          + " steps)");

    std::remove(data_file);
    std::remove(options_file);
    std::remove(config_file);
}

/***************************** Likelihood *****************************/

// The log likelihood in blocks equals the sum of the log densities
static void test_log_likelihood()
{
    std::mt19937_64 rng(7);
    std::uniform_real_distribution<double> u(0.0, 1.0);

    int num_bad = 0;
    for(int trial=0; trial<2000; ++trial)
    {
        // Sizes that are not multiples of the block, and parameters from
        // far beyond the range in which a block is multiplied out
        size_t n = 1 + static_cast<size_t>(60*u(rng));
        double sigma0 = std::exp(-60.0 + 120.0*u(rng));
        double sigma1 = std::exp(-60.0 + 120.0*u(rng));
        double nu = std::exp(std::log(1E3)*u(rng));
        double model_scale = std::exp(-30.0 + 60.0*u(rng));

        std::vector<double> y(n), model(n);
        for(size_t i=0; i<n; ++i)
        {
            model[i] = model_scale*u(rng);
            y[i] = model[i] + model_scale*(u(rng) - 0.5);
        }
        // Sometimes a variance that is not positive, which makes it NaN
        if(trial % 50 == 0)
            model[n/2] = -sigma0*sigma0/sigma1*(1.0 + u(rng));

        double fast = student_t_log_likelihood(y,
                                    [&model](size_t i) { return model[i]; },
                                    sigma0, sigma1, nu);
        double slow = 0.0, size = 0.0;
        for(size_t i=0; i<n; ++i)
        {
            double var = sigma0*sigma0 + sigma1*model[i];
            double term = student_t_log_pdf(y[i] - model[i], var, nu);
            slow += term;
            size += std::abs(term);
        }

        bool ok = (std::isfinite(fast) && std::isfinite(slow))
                        ? (std::abs(fast - slow) <= 1E-12*size)
                        : (std::isfinite(fast) == std::isfinite(slow));
        if(!ok)
        {
            if(num_bad < 5)
                std::cout<<"        n="<<n<<" sigma0="<<sigma0<<" sigma1="
                         <<sigma1<<" nu="<<nu<<": "<<fast<<" vs "<<slow
                         <<std::endl;
            ++num_bad;
        }
    }
    check(num_bad == 0,
          "log likelihood in blocks equals the sum of the log densities ("
          + str(num_bad) + " of 2000 cases differ)");
}

int main()
{
    test_student_t();
    test_piecewise_linear();
    test_background_knots();
    test_lookup();
    test_peaks_windowed();
    test_curve_updates();
    test_log_likelihood();

    if(num_failed > 0)
    {
        std::cout<<num_failed<<" check(s) failed."<<std::endl;
        return 1;
    }
    std::cout<<"All checks passed."<<std::endl;
    return 0;
}


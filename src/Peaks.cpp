#include "Peaks.h"
#include "Lookup.h"
#include <algorithm>
#include <cmath>

namespace AMORPH
{

// The half-width of the range of the lookup table, in widths of the peak
static const double table_half_width = 20.0;

std::pair<std::size_t, std::size_t> peak_window(const std::vector<double>& x,
                                                double c, double w_inv)
{
    // (x[j] - c)*w_inv does not decrease with j, so the points where it is
    // below -20 come first and those where it is above 20 come last. The
    // tests are the same expression as in the evaluation, so the window
    // holds exactly the points with |(x[j] - c)*w_inv| <= 20. A NaN (a peak
    // of zero width, at x[j] = c) fails both tests and is left out, as
    // |NaN| <= 20 is false.
    auto below = [c, w_inv](double xj, double bound)
                 { return (xj - c)*w_inv < bound; };
    auto not_above = [c, w_inv](double xj, double bound)
                     { return (xj - c)*w_inv <= bound; };

    auto first = std::lower_bound(x.begin(), x.end(), -table_half_width,
                                  below);
    auto last = std::lower_bound(first, x.end(), table_half_width,
                                 not_above);
    return std::make_pair(static_cast<std::size_t>(first - x.begin()),
                          static_cast<std::size_t>(last - x.begin()));
}

void add_peaks(const std::vector<std::vector<double>>& peaks, double shape,
               double sign, const std::vector<double>& x,
               std::vector<double>& y)
{
    const Lookup::Row profile = Lookup::row(shape);

    double c, w_inv, coeff;
    for(const auto& peak: peaks)
    {
        // {center, log_mass, width}
        c = peak[0];
        w_inv = 1.0/peak[2];
        coeff = sign*exp(peak[1])*w_inv;

        auto window = peak_window(x, c, w_inv);
        for(std::size_t j=window.first; j<window.second; ++j)
            y[j] += coeff*profile((x[j] - c)*w_inv);

        if(sign < 0.0)
            for(std::size_t j=window.first; j<window.second; ++j)
                y[j] = std::max(y[j], 0.0);
    }
}

} // namespace AMORPH


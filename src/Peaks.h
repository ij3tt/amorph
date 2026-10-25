#ifndef AMORPH_Peaks_h
#define AMORPH_Peaks_h

#include <cstddef>
#include <utility>
#include <vector>

/*
* The curves of the peaks on the grid of the data. A peak is
* {centre, log(mass), width}, and its profile is the shape tabulated by
* Lookup, which is zero beyond 20 widths from the centre.
*/

namespace AMORPH
{

// The points of the grid x (strictly increasing) within 20 widths of the
// centre c of a peak, where w_inv = 1/width: the range [first, last) of the
// indices j with |(x[j] - c)*w_inv| <= 20.
std::pair<std::size_t, std::size_t> peak_window(const std::vector<double>& x,
                                                double c, double w_inv);

// Add sign times the curves of the peaks, of shape log(nu), to the curve y
// on the grid x. A sign of -1 subtracts exactly what +1 added; since the
// curve of the peaks cannot be negative, a point that rounding takes below
// zero is set to zero.
void add_peaks(const std::vector<std::vector<double>>& peaks, double shape,
               double sign, const std::vector<double>& x,
               std::vector<double>& y);

} // namespace AMORPH

#endif


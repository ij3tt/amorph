#ifndef AMORPH_Background_h
#define AMORPH_Background_h

#include <vector>

namespace AMORPH
{

/*
* The piecewise linear background curve through four knots
* (x_knots[i], y_knots[i]). The inner knots x_knots[1] and x_knots[2] split
* the x-axis into three segments.
*/
double piecewise_linear(const std::vector<double>& x_knots,
                        const std::vector<double>& y_knots, double x);

} // namespace AMORPH

#endif


#include "Background.h"

namespace AMORPH
{

double piecewise_linear(const std::vector<double>& x_knots,
                        const std::vector<double>& y_knots, double x)
{
    // Which segment x is in
    size_t i = 0;
    if(x >= x_knots[1])
        i = (x < x_knots[2])?(1):(2);

    double x1 = x_knots[i];
    double x2 = x_knots[i+1];

    // Fractional position within the segment
    double lambda = (x - x1)/(x2 - x1);
    return (1.0 - lambda)*y_knots[i] + lambda*y_knots[i+1];
}

} // namespace AMORPH


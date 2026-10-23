#ifndef AMORPH_Likelihood_h
#define AMORPH_Likelihood_h

#include <cmath>

/*
* The Student-t sampling distribution of the data, with nu degrees of
* freedom and scale sqrt(var), where var = sigma0^2 + sigma1*model (see the
* table of priors in the paper). The log density of a residual r is
*     student_t_log_norm(nu) + student_t_log_kernel(r, var, nu).
* The first part only depends on nu, so the likelihood computes it once for
* all the data points.
*/

namespace AMORPH
{

// The part of the log density that only depends on nu
inline double student_t_log_norm(double nu)
{
    static constexpr double pi = 3.141592653589793;
    return std::lgamma(0.5*(nu + 1.0)) - std::lgamma(0.5*nu)
                - 0.5*std::log(pi*nu);
}

// The rest of the log density
inline double student_t_log_kernel(double r, double var, double nu)
{
    return -0.5*std::log(var)
                - 0.5*(nu + 1.0)*std::log(1.0 + r*r/(nu*var));
}

// The log density of a residual r
inline double student_t_log_pdf(double r, double var, double nu)
{
    return student_t_log_norm(nu) + student_t_log_kernel(r, var, nu);
}

} // namespace AMORPH

#endif


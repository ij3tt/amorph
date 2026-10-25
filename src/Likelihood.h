#ifndef AMORPH_Likelihood_h
#define AMORPH_Likelihood_h

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

/*
* The Student-t sampling distribution of the data, with nu degrees of
* freedom and scale sqrt(var), where var = sigma0^2 + sigma1*model (see the
* table of priors in the paper). The log density of a residual r is
*     student_t_log_norm(nu) + student_t_log_kernel(r, var, nu).
* The first part only depends on nu, so the likelihood computes it once for
* all the data points.
*
* Most of the time of the likelihood goes into the logs of the kernel. It
* takes the log of the product of each block of 8 points rather than the log
* of each point: a quarter of a log per point instead of two.
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

// The sum of the logs of x[0], ..., x[n-1], with n <= 8: the log of their
// product, if each is between 1E-38 and 1E38, so that the product of 8 of
// them can neither overflow nor underflow; otherwise the logs one by one,
// so that a number that is not positive gives what its log gives.
inline double sum_of_logs(const double* x, std::size_t n)
{
    bool in_range = true;
    double product = 1.0;
    for(std::size_t k=0; k<n; ++k)
    {
        in_range = in_range & (x[k] >= 1E-38) & (x[k] <= 1E38);
        product *= x[k];
    }
    if(in_range)
        return std::log(product);

    double sum = 0.0;
    for(std::size_t k=0; k<n; ++k)
        sum += std::log(x[k]);
    return sum;
}

// The log likelihood of the data y given the model curve, where model(i)
// is the curve at point i: the sum over i of
//     student_t_log_pdf(y[i] - model(i), sigma0^2 + sigma1*model(i), nu),
// up to rounding. Not finite if a term is not.
template<class Model>
double student_t_log_likelihood(const std::vector<double>& y,
                                const Model& model, double sigma0,
                                double sigma1, double nu)
{
    static const std::size_t block = 8;

    // Constants of the t distribution
    const double var0 = sigma0*sigma0;
    const double half_nu_plus_one = 0.5*(nu + 1.0);

    double var[block], t[block];
    double sum_log_var = 0.0, sum_log_t = 0.0;
    for(std::size_t start=0; start<y.size(); start+=block)
    {
        std::size_t size = std::min(block, y.size() - start);
        for(std::size_t k=0; k<size; ++k)
        {
            double m = model(start + k);
            double r = y[start + k] - m;
            var[k] = var0 + sigma1*m;
            t[k] = 1.0 + r*r/(nu*var[k]);
        }
        sum_log_var += sum_of_logs(var, size);
        sum_log_t += sum_of_logs(t, size);
    }

    return y.size()*student_t_log_norm(nu) - 0.5*sum_log_var
                - half_nu_plus_one*sum_log_t;
}

} // namespace AMORPH

#endif


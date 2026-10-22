/*
* Unit tests of the parts of the AMORPH model that can be checked without
* running the sampler. Run by ctest: the exit status is 1 if any check fails.
*/

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

#include "Background.h"
#include "Likelihood.h"
#include "Lookup.h"
#include "MyModel.h"

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

int main()
{
    test_student_t();
    test_piecewise_linear();
    test_background_knots();
    test_lookup();

    if(num_failed > 0)
    {
        std::cout<<num_failed<<" check(s) failed."<<std::endl;
        return 1;
    }
    std::cout<<"All checks passed."<<std::endl;
    return 0;
}


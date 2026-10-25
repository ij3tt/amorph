#ifndef AMORPH_Lookup_h
#define AMORPH_Lookup_h

#include <vector>

/*
* Lookup tables for speeding things up
* Singleton pattern
*/

namespace AMORPH
{

class Lookup
{
	private:
		int num_shape;
        double shape_min, shape_max, dshape, one_over_dshape;

        int num_x;
		double x_min, x_max, dx, one_over_dx;
		std::vector<std::vector<double>> f;

		Lookup();
		Lookup(const Lookup& other);

		static Lookup instance;

	public:
		static double evaluate(double shape, double x);

        // One shape of the table, for evaluating it at many x: row(shape)(x)
        // is evaluate(shape, x). It holds copies of the constants of the
        // table, so that a loop over x can keep them in registers.
        class Row
        {
            private:
                const double* f;
                double x_min, dx, one_over_dx;
                int num_x;

            public:
                Row(const double* f, const Lookup& table);
                double operator()(double x) const;
        };

        static Row row(double shape);
};

inline Lookup::Row::Row(const double* f, const Lookup& table)
:f(f)
,x_min(table.x_min)
,dx(table.dx)
,one_over_dx(table.one_over_dx)
,num_x(table.num_x)
{

}

// A null f is a shape outside the table
inline double Lookup::Row::operator()(double x) const
{
    int j = (int)((x - x_min) * one_over_dx);

    double frac = (x - (x_min + j*dx))*one_over_dx;

    if(f == nullptr || j < 0 || j >= (num_x - 1))
        return 0.0;

    return frac*f[j+1] + (1.0 - frac)*f[j];
}

inline Lookup::Row Lookup::row(double shape)
{
    int i = (int)((shape - instance.shape_min) * instance.one_over_dshape);
    if(i < 0 || i >= instance.num_shape)
        return Row(nullptr, instance);
    return Row(instance.f[i].data(), instance);
}

inline double Lookup::evaluate(double shape, double x)
{
    return row(shape)(x);
}

} // namespace AMORPH

#endif


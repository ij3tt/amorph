#ifndef AMORPH_Data_h
#define AMORPH_Data_h

#include <vector>

namespace AMORPH
{

/*
* An object of this class is a dataset, from which we do the inference.
*/
class Data
{
    private:
        // Data x and y
        std::vector<double> x;
        std::vector<double> y;

        // Some summaries
        double x_min, x_max, x_range;

        // Whether the data has been loaded or not
        bool loaded;

    public:
        // Construct as empty dataset
        Data();

        // Load data from a text file of two columns, x and y. Throws
        // std::runtime_error if the file cannot be read or is not valid.
        void load(const char* filename);

        // Getters (by reference - use caution)
        const std::vector<double>& get_x() const { return x; }
        const std::vector<double>& get_y() const { return y; }

        // More getters (not by reference)
        double get_x_min() const { return x_min; }
        double get_x_max() const { return x_max; }
        double get_x_range() const { return x_range; }
        bool get_loaded() const { return loaded; }

        // Calculate the summaries (throws std::logic_error if there is no data)
        void compute_summaries();
};

} // namespace AMORPH

#endif


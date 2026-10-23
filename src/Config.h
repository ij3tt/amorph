#ifndef AMORPH_Config_h
#define AMORPH_Config_h

#include <cstddef>
#include <string>
#include <tuple>
#include <vector>

namespace AMORPH
{

class Config
{
    private:

        std::size_t num_threads;

        std::string data_file;
        std::string dnest4_options_file;

        std::tuple<double, double> control_points;

        std::size_t max_num_narrow_peaks;
        std::size_t max_num_wide_peaks;

        double left_edge, right_edge;

        // Mock "command line options": the strings, and pointers to them
        // followed by a null pointer, like the argv of main()
        std::vector<std::string> args;
        std::vector<char*> argv;

    public:

        Config();
        Config(const Config& other) = delete;
        Config(Config&& other) = delete;
        Config& operator = (const Config& other) = delete;

        // Load from YAML file. Throws std::runtime_error, with the file name
        // and the line in the message, if the file cannot be read or a
        // setting is missing or invalid.
        void load(const char* filename);

        // Getters
        const std::string& get_data_file() const { return data_file; }
        int get_argc() const { return static_cast<int>(args.size()); }
        char** get_argv() { return argv.data(); }
        const std::tuple<double, double> get_control_points() const
        { return control_points; }
        std::size_t get_max_num_narrow_peaks() const
        { return max_num_narrow_peaks; }
        std::size_t get_max_num_wide_peaks() const
        { return max_num_wide_peaks; }
        double get_left_edge() const { return left_edge; }
        double get_right_edge() const { return right_edge; }

        // A global instance
        static Config global;

};

} // namespace AMORPH

#endif


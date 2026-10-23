#include "Config.h"
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <yaml-cpp/yaml.h>

namespace AMORPH
{

// Static instance
Config Config::global;

/*
* Helpers for reading the settings. They throw std::runtime_error with a
* message that names the file, the line and the key, such as
* "config.yaml, line 5: 'num_threads' must be at least 1, got '0'".
*/

// The start of an error message about a value in the file. An empty value
// has no line: yaml-cpp gives it the line of what comes next.
static std::string where(const std::string& filename, const YAML::Node& node)
{
    std::stringstream s;
    s<<filename;
    YAML::Mark mark = node.Mark();
    if(!mark.is_null() && !node.IsNull())
        s<<", line "<<(mark.line + 1);
    return s.str();
}

// A short description of a value, for the error messages
static std::string describe(const YAML::Node& node)
{
    std::stringstream s;
    if(node.IsScalar())
        s<<"'"<<node.Scalar()<<"'";
    else if(node.IsSequence())
        s<<"a list of "<<node.size()<<((node.size() == 1)?" value":" values");
    else if(node.IsMap())
        s<<"a group of settings";
    else
        s<<"nothing";
    return s.str();
}

// The value of a key in a group of settings. path is the full name of the
// key, such as 'inference_assumptions.control_points'.
static YAML::Node get_value(const std::string& filename,
                            const YAML::Node& group,
                            const std::string& key, const std::string& path)
{
    const YAML::Node value = group[key];
    if(!value.IsDefined())
        throw std::runtime_error(filename + ": missing key '" + path + "'");
    return value;
}

// The value of a key that holds a group of settings
static YAML::Node get_group(const std::string& filename,
                            const YAML::Node& group,
                            const std::string& key, const std::string& path)
{
    YAML::Node value = get_value(filename, group, key, path);
    if(!value.IsMap())
        throw std::runtime_error(where(filename, value) + ": '" + path
                                 + "' must be a group of settings, got "
                                 + describe(value));
    return value;
}

// A finite number
static double to_number(const std::string& filename, const YAML::Node& value,
                        const std::string& what)
{
    double result;
    if(!YAML::convert<double>::decode(value, result)
            || !std::isfinite(result))
        throw std::runtime_error(where(filename, value) + ": " + what
                                 + " must be a number, got "
                                 + describe(value));
    return result;
}

// A whole number, at least 1
static std::size_t get_count(const std::string& filename,
                             const YAML::Node& group,
                             const std::string& key, const std::string& path)
{
    const YAML::Node value = get_value(filename, group, key, path);
    long long result;
    if(!YAML::convert<long long>::decode(value, result))
        throw std::runtime_error(where(filename, value) + ": '" + path
                                 + "' must be a whole number, got "
                                 + describe(value));
    if(result < 1)
        throw std::runtime_error(where(filename, value) + ": '" + path
                                 + "' must be at least 1, got "
                                 + describe(value));
    return static_cast<std::size_t>(result);
}

// The name of a file that can be read
static std::string get_file(const std::string& filename,
                            const YAML::Node& group,
                            const std::string& key, const std::string& path)
{
    const YAML::Node value = get_value(filename, group, key, path);
    if(!value.IsScalar())
        throw std::runtime_error(where(filename, value) + ": '" + path
                                 + "' must be a file name, got "
                                 + describe(value));

    std::string result = value.Scalar();
    std::ifstream fin(result.c_str());
    if(!fin)
        throw std::runtime_error(where(filename, value)
                                 + ": cannot open the file '" + result
                                 + "' given by '" + path + "' (relative "
                                 + "paths start from the folder AMORPH "
                                 + "runs in)");
    return result;
}

Config::Config()
:num_threads(0)
,control_points(0.0, 0.0)
,max_num_narrow_peaks(0)
,max_num_wide_peaks(0)
,left_edge(0.0)
,right_edge(0.0)
,narrow_peak_nu_min(0.1)
,narrow_peak_nu_max(100.0)
{

}

void Config::load(const char* filename)
{
    if(!args.empty())
    {
        std::cerr << "Don't load config twice." << std::endl;
        return;
    }

    // Parse the YAML file
    std::ifstream fin(filename);
    if(!fin)
        throw std::runtime_error(std::string("cannot open '") + filename
                                 + "': it must be in the folder AMORPH "
                                 + "runs in");
    YAML::Node config;
    try
    {
        config = YAML::Load(fin);
    }
    catch(const YAML::Exception& e)
    {
        std::stringstream s;
        s<<filename;
        if(!e.mark.is_null())
            s<<", line "<<(e.mark.line + 1);
        s<<": YAML syntax error: "<<e.msg;
        throw std::runtime_error(s.str());
    }

    // An empty file has no settings, rather than settings of the wrong type
    if(config.IsNull())
        config = YAML::Node(YAML::NodeType::Map);
    if(!config.IsMap())
        throw std::runtime_error(std::string(filename) + ": expected "
                                 + "settings such as 'num_threads: 8', got "
                                 + describe(config));

    // Read everything into temporaries first, so that nothing changes if
    // the file turns out to be invalid
    const std::string f(filename);
    std::size_t new_num_threads = get_count(f, config, "num_threads",
                                            "num_threads");
    std::string new_data_file = get_file(f, config, "data_file", "data_file");
    std::string new_dnest4_options_file = get_file(f, config,
                                                   "dnest4_options_file",
                                                   "dnest4_options_file");

    const std::string ia = "inference_assumptions";
    const YAML::Node assumptions = get_group(f, config, ia, ia);

    const std::string cp_path = ia + ".control_points";
    const YAML::Node cps = get_value(f, assumptions, "control_points",
                                     cp_path);
    if(!cps.IsSequence() || cps.size() != 2)
        throw std::runtime_error(where(f, cps) + ": '" + cp_path
                                 + "' must be a list of two numbers, such "
                                 + "as [10.0, 40.0], got " + describe(cps));
    double cp1 = to_number(f, cps[0], "the first of '" + cp_path + "'");
    double cp2 = to_number(f, cps[1], "the second of '" + cp_path + "'");
    if(!(cp1 < cp2))
        throw std::runtime_error(where(f, cps) + ": '" + cp_path
                                 + "' must be in increasing order, got "
                                 + describe(cps[0]) + " and "
                                 + describe(cps[1]));

    std::size_t new_max_num_narrow_peaks
                = get_count(f, assumptions, "max_num_narrow_peaks",
                            ia + ".max_num_narrow_peaks");
    std::size_t new_max_num_wide_peaks
                = get_count(f, assumptions, "max_num_wide_peaks",
                            ia + ".max_num_wide_peaks");

    const std::string le_path = ia + ".left_edge";
    const std::string re_path = ia + ".right_edge";
    const YAML::Node le = get_value(f, assumptions, "left_edge", le_path);
    const YAML::Node re = get_value(f, assumptions, "right_edge", re_path);
    double new_left_edge = to_number(f, le, "'" + le_path + "'");
    double new_right_edge = to_number(f, re, "'" + re_path + "'");
    if(new_left_edge < 0.0)
        throw std::runtime_error(where(f, le) + ": '" + le_path
                                 + "' must be at least 0, got "
                                 + describe(le));
    if(new_right_edge > 1.0)
        throw std::runtime_error(where(f, re) + ": '" + re_path
                                 + "' must be at most 1, got "
                                 + describe(re));
    if(!(new_left_edge < new_right_edge))
        throw std::runtime_error(where(f, le) + ": '" + le_path
                                 + "' must be less than '" + re_path
                                 + "', got " + describe(le) + " and "
                                 + describe(re));

    // Optional: the bounds of nu of the narrow peaks, 0.1 to 100 as in the
    // paper by default. The table of peak shapes (Lookup.cpp) covers just
    // that range.
    double new_nu_min = 0.1;
    double new_nu_max = 100.0;
    const std::string nu_path = ia + ".narrow_peak_nu";
    const YAML::Node nus = assumptions["narrow_peak_nu"];
    if(nus.IsDefined())
    {
        if(!nus.IsSequence() || nus.size() != 2)
            throw std::runtime_error(where(f, nus) + ": '" + nu_path
                                     + "' must be a list of two numbers, "
                                     + "such as [0.1, 100.0], got "
                                     + describe(nus));
        new_nu_min = to_number(f, nus[0], "the first of '" + nu_path + "'");
        new_nu_max = to_number(f, nus[1], "the second of '" + nu_path + "'");
        if(!(new_nu_min < new_nu_max))
            throw std::runtime_error(where(f, nus) + ": '" + nu_path
                                     + "' must be in increasing order, got "
                                     + describe(nus[0]) + " and "
                                     + describe(nus[1]));
        if(new_nu_min < 0.1 || new_nu_max > 100.0)
            throw std::runtime_error(where(f, nus) + ": '" + nu_path
                                     + "' must lie between 0.1 and 100, the "
                                     + "range of the table of peak shapes, "
                                     + "got " + describe(nus[0]) + " and "
                                     + describe(nus[1]));
    }

    // Optional: the seed of the random number generator. DNest4 takes an
    // unsigned int; without a seed it uses the time.
    std::string new_seed;
    const YAML::Node seed_node = config["seed"];
    if(seed_node.IsDefined())
    {
        long long value;
        if(!YAML::convert<long long>::decode(seed_node, value)
                || value < 0 || value > 4294967295LL)
            throw std::runtime_error(where(f, seed_node) + ": 'seed' must be "
                                     + "a whole number from 0 to "
                                     + "4294967295, got "
                                     + describe(seed_node));
        new_seed = std::to_string(value);
    }

    // All good
    num_threads = new_num_threads;
    data_file = new_data_file;
    dnest4_options_file = new_dnest4_options_file;
    control_points = std::make_tuple(cp1, cp2);
    max_num_narrow_peaks = new_max_num_narrow_peaks;
    max_num_wide_peaks = new_max_num_wide_peaks;
    left_edge = new_left_edge;
    right_edge = new_right_edge;
    narrow_peak_nu_min = new_nu_min;
    narrow_peak_nu_max = new_nu_max;
    seed = new_seed;

    std::stringstream ss;
    ss << num_threads;
    args = {"main", "-t", ss.str(), "-d", data_file,
            "-o", dnest4_options_file};
    if(!seed.empty())
    {
        args.push_back("-s");
        args.push_back(seed);
    }
    for(std::string& arg: args)
        argv.push_back(&arg[0]);
    argv.push_back(nullptr);
}

} // namespace AMORPH


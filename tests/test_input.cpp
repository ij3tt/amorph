/*
* Unit tests of the checks of the input files: the data file and
* config.yaml. Run by ctest: the exit status is 1 if any check fails.
*
* Usage: test_input [path/to/src]
* With the path to the src directory, the bundled datasets are read too.
* The temporary files are written to the current directory.
*/

#include <cstddef>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

#include "Config.h"
#include "Data.h"
#include "MyModel.h"

using namespace AMORPH;

static int num_failed = 0;

// Report a check without stopping, so that one run shows all the failures
static void check(bool ok, const std::string& what)
{
    std::cout<<(ok?"ok      ":"FAILED  ")<<what<<std::endl;
    if(!ok)
        ++num_failed;
}

static std::string str(double x)
{
    std::stringstream ss;
    ss<<x;
    return ss.str();
}

// Run f, which must throw a std::runtime_error whose message contains
// fragment
template<class Function>
static void check_error(Function f, const std::string& fragment,
                        const std::string& what)
{
    std::string message = "no exception";
    bool ok = false;
    try
    {
        f();
    }
    catch(const std::runtime_error& e)
    {
        message = e.what();
        ok = (message.find(fragment) != std::string::npos);
    }
    check(ok, what + ": " + message);
}

// Write a file. Binary mode, so that "\r\n" stays as it is.
static void write_file(const std::string& filename,
                       const std::string& contents)
{
    std::ofstream fout(filename.c_str(), std::ios::binary);
    fout<<contents;
}

static const std::string data_file = "test_input_data.txt";
static const std::string config_file = "test_input_config.yaml";
static const std::string options_file = "test_input_options.txt";
static const std::string missing_file = "test_input_missing.txt";

/******************************* Data *******************************/

// n data points from x = 10 to 40, one per line
static std::string data_lines(int n)
{
    std::stringstream ss;
    for(int i=0; i<n; ++i)
        ss<<(10.0 + 30.0*i/(n - 1))<<' '<<(100.0 + i)<<'\n';
    return ss.str();
}

// Load contents written to the data file, which must fail with a message
// that contains fragment
static void check_data_error(const std::string& contents,
                             const std::string& fragment,
                             const std::string& what)
{
    write_file(data_file, contents);
    check_error([]()
                {
                    Data data;
                    data.load(data_file.c_str());
                }, fragment, what);
}

static void test_data_errors()
{
    std::remove(missing_file.c_str());
    check_error([]()
                {
                    Data data;
                    data.load(missing_file.c_str());
                }, "cannot open the data file '" + missing_file + "'",
                "missing data file");

    // The bad line is line 4 of the file: line 1 is a comment
    std::string good = "# x y\n10 1\n11 2\n";
    std::string rest = data_lines(10);
    std::string at_line_4 = data_file + ", line 4: expected two numbers";
    check_data_error(good + "12 abc\n" + rest, at_line_4,
                     "line with text");
    check_data_error(good + "12\n" + rest, at_line_4, "line with one number");
    check_data_error(good + "12 3 4\n" + rest, at_line_4,
                     "line with three numbers");
    check_data_error(good + "12;3\n" + rest, at_line_4,
                     "line with a semicolon");
    check_data_error(good + "12,,3\n" + rest, at_line_4,
                     "line with two commas");
    check_data_error(good + "12-3\n" + rest, at_line_4,
                     "line without a separator");
    check_data_error(good + "12 3abc\n" + rest, at_line_4,
                     "line with text after the numbers");
    check_data_error(good + "12 nan\n" + rest, at_line_4, "line with nan");
    check_data_error(good + "12 1e999\n" + rest, at_line_4,
                     "line with a number that is too large");
    check_data_error("2Theta Intensity\n" + rest,
                     data_file + ", line 1: expected two numbers",
                     "header line that is not a comment");

    check_data_error("", data_file + ": found 0 data points, at least 10 "
                     "are needed", "empty file");
    check_data_error("# x y\n\n# nothing else\n", "found 0 data points",
                     "file with comments only");
    check_data_error(data_lines(9), "found 9 data points, at least 10",
                     "9 data points");

    // x must be strictly increasing: line 6 repeats the x of line 5
    std::string start = "# x y\n10 1\n11 2\n\n12 3\n";
    check_data_error(start + "12 4\n" + data_lines(10),
                     data_file + ", line 6: the x values must be strictly "
                     "increasing, but x = 12 follows x = 12 (line 5)",
                     "repeated x");
    check_data_error(start + "11.5 4\n" + data_lines(10),
                     data_file + ", line 6: the x values must be strictly "
                     "increasing, but x = 11.5 follows x = 12 (line 5)",
                     "decreasing x");
}

static void test_data_valid()
{
    // Comments and blank lines anywhere, Windows line endings, tabs, commas
    // and no line break at the end
    write_file(data_file, "\xEF\xBB\xBF# Scan Data\r\n"
                          "# 01/29/12\r\n"
                          "10.0     41\r\n"
                          "10.02\t45\r\n"
                          "\r\n"
                          "  # a comment in the middle\r\n"
                          "10.04,55\r\n"
                          "10.06, 56\r\n"
                          "10.08 ,57\r\n"
                          "   10.1\t \t-5e-1  \r\n"
                          "\t\r\n"
                          "10.12 1E2\r\n"
                          "10.14 0\r\n"
                          "10.16 3\r\n"
                          "10.18 4");
    Data data;
    bool threw = false;
    try
    {
        data.load(data_file.c_str());
    }
    catch(const std::exception& e)
    {
        threw = true;
        std::cout<<e.what()<<std::endl;
    }
    const std::vector<double>& x = data.get_x();
    const std::vector<double>& y = data.get_y();
    check(!threw && data.get_loaded(), "file with comments, blank lines, "
          "CRLF, tabs and commas is read");
    check(x.size() == 10 && y.size() == 10,
          "it has 10 data points: " + str(x.size()));
    if(x.size() == 10 && y.size() == 10)
    {
        check(x[0] == 10.0 && y[0] == 41.0 && x[5] == 10.1 && y[5] == -0.5
              && y[6] == 100.0 && x[9] == 10.18 && y[9] == 4.0,
              "its values are read correctly");
        check(data.get_x_min() == 10.0 && data.get_x_max() == 10.18,
              "x_min and x_max: " + str(data.get_x_min()) + " "
              + str(data.get_x_max()));
    }

    // An invalid file leaves the data as they were
    write_file(data_file, data_lines(5));
    threw = false;
    try
    {
        data.load(data_file.c_str());
    }
    catch(const std::runtime_error&)
    {
        threw = true;
    }
    check(threw && data.get_x().size() == 10 && data.get_loaded(),
          "a failed load keeps the previous data");
}

// The datasets in src/, read as before: the same number of points
static void test_bundled_datasets(const std::string& src)
{
    struct Dataset
    {
        std::string name;
        std::size_t num_points;
        double x_min, x_max;
    };
    std::vector<Dataset> datasets{
        {"0%glass_rhyolite_Emperyon.txt", 1731, 5.01313028, 49.99313028},
        {"50% glass .02step3secdwell.txt", 1501, 10.0, 40.0},
        {"90%_glass_basalt_Emperyon.txt", 1731, 5.01313028, 49.99313028},
        {"easy_data.txt", 1001, 0.0, 50.0},
        {"G30RAW.txt", 3251, 5.0, 70.0},
        {"G30RAW_15-70.txt", 2751, 15.0, 70.0},
        {"G30RAW_20-50.txt", 1501, 20.0, 50.0},
        {"G30RAW_amorph.txt", 1001, 26.0, 46.0},
        {"N3RAW.txt", 3251, 5.0, 70.0},
        {"N3RAW_15-70.txt", 2751, 15.0, 70.0},
        {"N3RAW_20-50.txt", 1501, 20.0, 50.0},
        {"N3RAW_amorph.txt", 1001, 26.0, 46.0}};

    for(const Dataset& d: datasets)
    {
        Data data;
        std::string message = "read";
        try
        {
            data.load((src + "/" + d.name).c_str());
        }
        catch(const std::exception& e)
        {
            message = e.what();
        }
        check(data.get_x().size() == d.num_points
              && data.get_x_min() == d.x_min && data.get_x_max() == d.x_max,
              "bundled dataset " + d.name + ": " + message + ", "
              + str(data.get_x().size()) + " points from "
              + str(data.get_x_min()) + " to " + str(data.get_x_max()));
    }
}

// The warning about control points outside the data (data from 10 to 40)
static void test_control_points_warning()
{
    write_file(data_file, data_lines(31));
    MyModel::set_control_points(std::make_tuple(10.0, 40.0));
    MyModel::load_data(data_file.c_str());
    check(MyModel::control_points_warning().empty(),
          "no warning for control points on the edges of the data");

    MyModel::set_control_points(std::make_tuple(12.0, 38.0));
    check(MyModel::control_points_warning().empty(),
          "no warning for control points inside the data");

    MyModel::set_control_points(std::make_tuple(5.0, 40.0));
    std::string warning = MyModel::control_points_warning();
    check(warning.find("outside the range of the data (10 to 40)")
                != std::string::npos,
          "warning for a control point below the data: " + warning);

    MyModel::set_control_points(std::make_tuple(10.0, 45.0));
    warning = MyModel::control_points_warning();
    check(!warning.empty(),
          "warning for a control point above the data: " + warning);
}

/****************************** Config ******************************/

// A valid config.yaml, laid out like src/config.yaml. Line 1 is the comment.
static const std::vector<std::string> config_lines{
    "# Set up everything for an AMORPH run",
    "---",
    "num_threads: 8",
    "data_file: \"" + data_file + "\"",
    "dnest4_options_file: \"" + options_file + "\"",
    "inference_assumptions:",
    "    control_points: [10.0, 40.0]",
    "    max_num_narrow_peaks: 500",
    "    max_num_wide_peaks: 100",
    "    left_edge: 0.3",
    "    right_edge: 0.7"};

// The valid configuration with the line of key replaced by 'key: value',
// or removed if remove is true
static std::string config_with(const std::string& key,
                               const std::string& value, bool remove=false)
{
    std::string result;
    for(const std::string& line: config_lines)
    {
        std::size_t first = line.find_first_not_of(' ');
        if(line.compare(first, key.size() + 1, key + ":") != 0)
            result += line + "\n";
        else if(!remove)
            result += line.substr(0, first) + key + ": " + value + "\n";
    }
    return result;
}

static std::string config_without(const std::string& key)
{
    return config_with(key, "", true);
}

// Load contents written to the config file, which must fail with a message
// that contains fragment
static void check_config_error(const std::string& contents,
                               const std::string& fragment,
                               const std::string& what)
{
    write_file(config_file, contents);
    check_error([]()
                {
                    Config c;
                    c.load(config_file.c_str());
                }, fragment, what);
}

static void test_config_valid()
{
    write_file(data_file, data_lines(20));
    write_file(options_file, "# DNest4 options\n");
    write_file(config_file, config_with("num_threads", "8"));

    Config c;
    bool threw = false;
    try
    {
        c.load(config_file.c_str());
    }
    catch(const std::exception& e)
    {
        threw = true;
        std::cout<<e.what()<<std::endl;
    }
    check(!threw, "valid config is read");
    check(c.get_data_file() == data_file, "data_file: " + c.get_data_file());
    check(c.get_control_points() == std::make_tuple(10.0, 40.0),
          "control_points");
    check(c.get_max_num_narrow_peaks() == 500
          && c.get_max_num_wide_peaks() == 100, "maximum numbers of peaks");
    check(c.get_left_edge() == 0.3 && c.get_right_edge() == 0.7,
          "left_edge and right_edge");

    std::vector<std::string> expected{"main", "-t", "8", "-d", data_file,
                                      "-o", options_file};
    char** argv = c.get_argv();
    bool same = (c.get_argc() == 7);
    for(std::size_t i=0; same && i<expected.size(); ++i)
        same = (argv[i] != nullptr && std::string(argv[i]) == expected[i]);
    check(same && argv[7] == nullptr,
          "command line options for DNest4: -t 8 -d ... -o ...");

    // The extreme values that are allowed
    std::string contents = config_with("left_edge", "0");
    contents.replace(contents.find("right_edge: 0.7"), 15, "right_edge: 1");
    write_file(config_file, contents);
    threw = false;
    try
    {
        Config c2;
        c2.load(config_file.c_str());
        check(c2.get_left_edge() == 0.0 && c2.get_right_edge() == 1.0,
              "left_edge = 0 and right_edge = 1 are allowed");
    }
    catch(const std::exception& e)
    {
        check(false, std::string("left_edge = 0 and right_edge = 1 are "
                                 "allowed: ") + e.what());
    }
}

static void test_config_errors()
{
    // The files that the valid configuration refers to
    write_file(data_file, data_lines(20));
    write_file(options_file, "# DNest4 options\n");

    const std::string& f = config_file;
    std::remove(missing_file.c_str());
    check_error([]()
                {
                    Config c;
                    c.load(missing_file.c_str());
                }, "cannot open '" + missing_file + "'",
                "missing config file");

    // Syntax errors: a value with a wrong indentation, an unclosed list
    std::string contents = config_with("left_edge", "0.3\n   right_edge: 0.7");
    check_config_error(contents, f + ", line 11: YAML syntax error",
                       "wrong indentation");
    check_config_error(config_with("num_threads", "[8"),
                       f + ", line 4: YAML syntax error",
                       "unclosed list");

    check_config_error("", f + ": missing key 'num_threads'", "empty file");
    check_config_error("- 8\n- 9\n", f + ": expected settings",
                       "file with a list");

    // Missing keys
    for(const std::string key: {"num_threads", "data_file",
                                "dnest4_options_file"})
        check_config_error(config_without(key),
                           f + ": missing key '" + key + "'",
                           "missing " + key);
    std::string top;
    for(std::size_t i=0; i<5; ++i)
        top += config_lines[i] + "\n";
    check_config_error(top, f + ": missing key 'inference_assumptions'",
                       "missing inference_assumptions");
    for(const std::string key: {"control_points", "max_num_narrow_peaks",
                                "max_num_wide_peaks", "left_edge",
                                "right_edge"})
        check_config_error(config_without(key),
                           f + ": missing key 'inference_assumptions."
                           + key + "'", "missing " + key);

    // Values of the wrong type
    check_config_error(config_with("num_threads", "eight"),
                       f + ", line 3: 'num_threads' must be a whole number, "
                       "got 'eight'", "num_threads is text");
    check_config_error(config_with("num_threads", "2.5"),
                       "'num_threads' must be a whole number",
                       "num_threads is not a whole number");
    check_config_error(config_with("num_threads", ""),
                       f + ": 'num_threads' must be a whole number, got "
                       "nothing", "num_threads has no value");
    check_config_error(config_with("data_file", "[a.txt, b.txt]"),
                       f + ", line 4: 'data_file' must be a file name",
                       "data_file is a list");
    check_config_error(top + "inference_assumptions: 5\n",
                       f + ", line 6: 'inference_assumptions' must be a "
                       "group of settings, got '5'",
                       "inference_assumptions is a number");
    check_config_error(config_with("control_points", "10.0"),
                       f + ", line 7: 'inference_assumptions.control_points'"
                       " must be a list of two numbers",
                       "control_points is a number");
    check_config_error(config_with("control_points", "[10.0, abc]"),
                       "the second of 'inference_assumptions.control_points'"
                       " must be a number, got 'abc'",
                       "control_points holds text");
    check_config_error(config_with("max_num_narrow_peaks", "many"),
                       f + ", line 8: 'inference_assumptions."
                       "max_num_narrow_peaks' must be a whole number",
                       "max_num_narrow_peaks is text");
    check_config_error(config_with("max_num_wide_peaks", "1e2"),
                       f + ", line 9: 'inference_assumptions."
                       "max_num_wide_peaks' must be a whole number",
                       "max_num_wide_peaks is not a whole number");
    check_config_error(config_with("left_edge", "[0.3]"),
                       f + ", line 10: 'inference_assumptions.left_edge' "
                       "must be a number, got a list of 1 value",
                       "left_edge is a list");
    check_config_error(config_with("right_edge", ".nan"),
                       f + ", line 11: 'inference_assumptions.right_edge' "
                       "must be a number", "right_edge is nan");

    // Invalid values
    check_config_error(config_with("num_threads", "0"),
                       f + ", line 3: 'num_threads' must be at least 1, "
                       "got '0'", "num_threads = 0");
    check_config_error(config_with("num_threads", "-2"),
                       "'num_threads' must be at least 1", "num_threads < 0");
    check_config_error(config_with("data_file", missing_file),
                       f + ", line 4: cannot open the file '" + missing_file
                       + "' given by 'data_file'", "data file is missing");
    check_config_error(config_with("dnest4_options_file", missing_file),
                       f + ", line 5: cannot open the file '" + missing_file
                       + "' given by 'dnest4_options_file'",
                       "DNest4 options file is missing");
    check_config_error(config_with("control_points", "[10.0, 40.0, 50.0]"),
                       "must be a list of two numbers, such as [10.0, 40.0], "
                       "got a list of 3 values", "three control points");
    check_config_error(config_with("control_points", "[40.0, 10.0]"),
                       f + ", line 7: 'inference_assumptions.control_points'"
                       " must be in increasing order, got '40.0' and '10.0'",
                       "control points in decreasing order");
    check_config_error(config_with("control_points", "[10.0, 10.0]"),
                       "must be in increasing order",
                       "equal control points");
    check_config_error(config_with("max_num_narrow_peaks", "0"),
                       f + ", line 8: 'inference_assumptions."
                       "max_num_narrow_peaks' must be at least 1",
                       "max_num_narrow_peaks = 0");
    check_config_error(config_with("max_num_wide_peaks", "0"),
                       f + ", line 9: 'inference_assumptions."
                       "max_num_wide_peaks' must be at least 1",
                       "max_num_wide_peaks = 0");
    check_config_error(config_with("left_edge", "-0.1"),
                       f + ", line 10: 'inference_assumptions.left_edge' "
                       "must be at least 0, got '-0.1'", "left_edge < 0");
    check_config_error(config_with("right_edge", "1.5"),
                       f + ", line 11: 'inference_assumptions.right_edge' "
                       "must be at most 1, got '1.5'", "right_edge > 1");
    contents = config_with("left_edge", "0.7");
    contents.replace(contents.find("right_edge: 0.7"), 15, "right_edge: 0.3");
    check_config_error(contents,
                       f + ", line 10: 'inference_assumptions.left_edge' "
                       "must be less than 'inference_assumptions.right_edge'"
                       ", got '0.7' and '0.3'", "left_edge > right_edge");
    check_config_error(config_with("left_edge", "0.7"),
                       "must be less than", "left_edge = right_edge");
}

// The optional settings: narrow_peak_nu and seed, added at the end of the
// valid configuration (line 12)
static void test_config_optional()
{
    write_file(data_file, data_lines(20));
    write_file(options_file, "# DNest4 options\n");

    const std::string valid = config_with("num_threads", "8");
    write_file(config_file, valid);
    try
    {
        Config c;
        c.load(config_file.c_str());
        check(c.get_narrow_peak_nu_min() == 0.1
              && c.get_narrow_peak_nu_max() == 100.0,
              "narrow_peak_nu is [0.1, 100] by default");
        check(c.get_seed().empty() && c.get_argc() == 7,
              "no seed by default");
    }
    catch(const std::exception& e)
    {
        check(false, std::string("valid config without the optional "
                                 "settings: ") + e.what());
    }

    write_file(config_file, valid + "    narrow_peak_nu: [1.0, 50.0]\n"
                            + "seed: 42\n");
    try
    {
        Config c;
        c.load(config_file.c_str());
        check(c.get_narrow_peak_nu_min() == 1.0
              && c.get_narrow_peak_nu_max() == 50.0,
              "narrow_peak_nu: [1.0, 50.0] is read");
        char** argv = c.get_argv();
        check(c.get_argc() == 9 && std::string(argv[7]) == "-s"
              && std::string(argv[8]) == "42" && argv[9] == nullptr,
              "seed: 42 becomes -s 42 for DNest4");
    }
    catch(const std::exception& e)
    {
        check(false, std::string("valid config with narrow_peak_nu and "
                                 "seed: ") + e.what());
    }

    const std::string& f = config_file;
    const std::string nu = "    narrow_peak_nu: ";
    check_config_error(valid + nu + "1.0\n",
                       f + ", line 12: 'inference_assumptions.narrow_peak_nu'"
                       " must be a list of two numbers",
                       "narrow_peak_nu is a number");
    check_config_error(valid + nu + "[1.0, many]\n",
                       "the second of 'inference_assumptions.narrow_peak_nu'"
                       " must be a number, got 'many'",
                       "narrow_peak_nu holds text");
    check_config_error(valid + nu + "[50.0, 1.0]\n",
                       f + ", line 12: 'inference_assumptions.narrow_peak_nu'"
                       " must be in increasing order, got '50.0' and '1.0'",
                       "narrow_peak_nu in decreasing order");
    check_config_error(valid + nu + "[0.05, 100.0]\n",
                       "must lie between 0.1 and 100", "narrow_peak_nu < 0.1");
    check_config_error(valid + nu + "[1.0, 200.0]\n",
                       "must lie between 0.1 and 100", "narrow_peak_nu > 100");

    check_config_error(valid + "seed: -1\n",
                       f + ", line 12: 'seed' must be a whole number from 0 "
                       "to 4294967295, got '-1'", "negative seed");
    check_config_error(valid + "seed: abc\n", "'seed' must be a whole number",
                       "seed is text");
    check_config_error(valid + "seed: 4294967296\n",
                       "'seed' must be a whole number", "seed too large");
}

int main(int argc, char** argv)
{
    test_data_errors();
    test_data_valid();
    if(argc > 1)
        test_bundled_datasets(argv[1]);
    else
        std::cout<<"skipped the bundled datasets: no path to src/ given"
                 <<std::endl;
    test_control_points_warning();
    test_config_valid();
    test_config_errors();
    test_config_optional();

    for(const std::string& filename: {data_file, config_file, options_file})
        std::remove(filename.c_str());

    if(num_failed > 0)
    {
        std::cout<<num_failed<<" check(s) failed."<<std::endl;
        return 1;
    }
    std::cout<<"All checks passed."<<std::endl;
    return 0;
}


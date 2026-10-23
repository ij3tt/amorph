#include "Data.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <fstream>
#include <iostream>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <string>

namespace AMORPH
{

// The smallest dataset that is accepted
static const std::size_t min_num_points = 10;

// Whether a line of the data file holds no data: it is empty or blank, or a
// comment (its first character that is not a space is '#')
static bool is_blank_or_comment(const std::string& line)
{
    std::size_t first = line.find_first_not_of(" \t\r\f\v");
    return first == std::string::npos || line[first] == '#';
}

// Read the two numbers on a line of the data file, separated by spaces or
// tabs, or by a comma (with or without spaces around it). Returns false if
// the line holds anything else.
static bool parse_line(const std::string& line, double& x, double& y)
{
    std::istringstream ss(line);
    ss.imbue(std::locale::classic());

    if(!(ss>>x))
        return false;

    // Something must separate the numbers
    int next = ss.peek();
    if(next != ' ' && next != '\t' && next != ',')
        return false;
    ss>>std::ws;
    if(ss.peek() == ',')
        ss.get();
    if(!(ss>>y))
        return false;

    // Nothing but white space may follow
    std::string rest;
    if(ss>>rest)
        return false;

    return std::isfinite(x) && std::isfinite(y);
}

// A line of the data file in quotes, shortened if it is long
static std::string quote(std::string line)
{
    std::size_t last = line.find_last_not_of(" \t\r\f\v");
    line.erase((last == std::string::npos)?0:(last + 1));
    if(line.size() > 60)
        line = line.substr(0, 57) + "...";
    return "'" + line + "'";
}

Data::Data()
:x_min(0.0)
,x_max(0.0)
,x_range(0.0)
,loaded(false)
{

}

void Data::load(const char* filename)
{
    // Open the file
    std::fstream fin(filename, std::ios::in);
    if(!fin)
        throw std::runtime_error(std::string("cannot open the data file '")
                                 + filename + "'");

    // Read into temporary vectors, so that nothing changes if the file
    // turns out to be invalid
    std::vector<double> new_x, new_y;

    std::string line;
    std::size_t line_number = 0;
    std::size_t previous_line_number = 0;
    while(std::getline(fin, line))
    {
        ++line_number;

        // A UTF-8 byte order mark, as some Windows editors write
        if(line_number == 1 && line.compare(0, 3, "\xEF\xBB\xBF") == 0)
            line.erase(0, 3);

        // Comments and blank lines may be anywhere in the file
        if(is_blank_or_comment(line))
            continue;

        double temp1, temp2;
        if(!parse_line(line, temp1, temp2))
        {
            std::stringstream s;
            s<<filename<<", line "<<line_number<<": expected two numbers "
             <<"(x and y), got "<<quote(line);
            throw std::runtime_error(s.str());
        }

        if(!new_x.empty() && !(temp1 > new_x.back()))
        {
            std::stringstream s;
            s.precision(12);
            s<<filename<<", line "<<line_number<<": the x values must be "
             <<"strictly increasing, but x = "<<temp1<<" follows x = "
             <<new_x.back()<<" (line "<<previous_line_number<<")";
            throw std::runtime_error(s.str());
        }

        new_x.push_back(temp1);
        new_y.push_back(temp2);
        previous_line_number = line_number;
    }

    if(new_x.size() < min_num_points)
    {
        std::stringstream s;
        s<<filename<<": found "<<new_x.size()<<" data points, at least "
         <<min_num_points<<" are needed";
        throw std::runtime_error(s.str());
    }

    x.swap(new_x);
    y.swap(new_y);

    // Print message to screen
    std::cout<<"# Read "<<x.size()<<" data points from file ";
    std::cout<<filename<<'.'<<std::endl;

    // Compute summaries
    compute_summaries();

    // Close the file
    fin.close();

    // Set flag
    loaded = true;
}

void Data::compute_summaries()
{
    if(x.empty())
        throw std::logic_error("Data::compute_summaries(): there is no data.");

    x_min = *std::min_element(x.begin(), x.end());
    x_max = *std::max_element(x.begin(), x.end());
    x_range = x_max - x_min;
}

} // namespace AMORPH


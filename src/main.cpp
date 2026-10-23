#include <exception>
#include <iostream>
#include <fstream>
#include <string>
#include "DNest4/code/DNest4.h"

// From this project
#include "Config.h"
#include "Data.h"
#include "MyModel.h"

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

using namespace AMORPH;

// Load the inputs and run the sampler. Invalid inputs throw exceptions.
static void run()
{
    // Load the config file
    Config::global.load("config.yaml");

    // Extract the mock command line options
    DNest4::CommandLineOptions clo(Config::global.get_argc(),
                                   Config::global.get_argv());

    // Set the control points
    AMORPH::MyModel::set_control_points(Config::global.get_control_points());

    // Load data
    AMORPH::MyModel::load_data(Config::global.get_data_file().c_str());

    // Run DNest4.
    DNest4::start<AMORPH::MyModel>(clo);
}

// AMORPH.exe started by a double click gets a console window of its own,
// which closes as soon as the program exits: wait for Enter there, so that
// the error message can be read. Never wait in a console that is shared
// with a shell (cmd, PowerShell, bash) or in CI, where nobody presses Enter.
static void wait_if_own_console()
{
#ifdef _WIN32
    DWORD processes[2];
    if(GetConsoleProcessList(processes, 2) == 1)
    {
        std::cerr<<"Press Enter to close this window."<<std::endl;
        std::string line;
        std::getline(std::cin, line);
    }
#endif
}

int main()
{
    try
    {
        run();
    }
    catch(const std::exception& e)
    {
        std::cerr<<"AMORPH: error: "<<e.what()<<std::endl;
        wait_if_own_console();
        return 1;
    }

    return 0;
}


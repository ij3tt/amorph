"""
Start the GUI of AMORPH, from src/:

    python -m amorph_gui [FILE] [--amorph PATH] [--runs FOLDER]
    python -m amorph_gui --self-test DIR [--amorph PATH]

FILE is a data file or a run archive (.amorph) to open.
"""

import argparse
import sys


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="python -m amorph_gui", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", nargs="?",
                   help="a data file or a run archive (.amorph) to open")
    p.add_argument("--amorph", metavar="PATH",
                   help="the AMORPH executable to run, instead of the one in "
                        "the settings")
    p.add_argument("--runs", metavar="FOLDER",
                   help="the folder of the runs, instead of the one in the "
                        "settings")
    p.add_argument("--self-test", metavar="DIR",
                   help="run easy_data.txt with tiny DNest4 options through "
                        "the GUI without a screen, post-process it, write the "
                        "archives and save a screenshot of every screen to "
                        "DIR")
    args = p.parse_args(argv)

    if args.self_test:
        from amorph_gui import selftest
        return selftest.main(args.self_test, amorph=args.amorph)

    # The splash first: loading the rest takes seconds, and a minute on the
    # first start of a newly unpacked package
    from amorph_gui import strings as S
    from amorph_gui.splash import show_splash
    splash = show_splash(sys.argv)
    splash.set_step(S.SPLASH_LIBRARIES)
    from amorph_gui.app import application
    app = application(sys.argv)
    splash.set_step(S.SPLASH_SCREENS)
    from amorph_gui.main_window import MainWindow
    from amorph_gui.preferences import Preferences
    window = MainWindow(Preferences(amorph=args.amorph, runs=args.runs))
    window.show()
    splash.finish(window)
    if args.file:
        if args.file.lower().endswith(".amorph"):
            window.open_archive(args.file)
        else:
            window.data_screen.open_data(args.file)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

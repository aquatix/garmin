import argparse
import json
import os
import sys


def parse_files(directory, target_directory):
    for filename in os.listdir(directory):
        if filename.endswith("_summary.json"):
            # parse summary, create graph
            continue
        elif filename.endswith(".json"):
            # parse wellness data
            continue
        else:
            continue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Garmin Data Scraper',
        epilog = 'Because the hell with APIs!', add_help = 'How to use',
        prog = 'python download.py [-u <user> | -c <csv fife with credentials>] [ -s <start_date> -e <end_date> -d <display_name> ] -o <output dir>')
    parser.add_argument('-i', '--input', required = False,
        help = 'Input directory.', default = os.path.join(os.getcwd(), 'Wellness/'))
    parser.add_argument('-o', '--output', required = False,
        help = 'Output directory.', default = os.path.join(os.getcwd(), 'Graphs/'))
    args = vars(parser.parse_args())

    # Sanity check, before we do anything:
    if args['input'] is None and args['output'] is None:
        print("Must specify an input (-i) directory for the Wellness data, and an output (-o) directory for graphs.")
        sys.exit()

    # Try to use the user argument from command line
    output = args['output']

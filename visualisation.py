import argparse
import json
import os
import sys
import jinja2


def add_totalsteps_to_summary(content):
    result = []
    totalsteps = 0
    for item in content:
        totalsteps = totalsteps + item['steps']
        item['totalsteps'] = totalsteps
        result.append(item)
    return result


def summary_to_graphdata(content):
    """Returns a list of datetime tuples with:
    {'datetime': ["2017-08-12T22:00:00.0", ..],
     'totalsteps': [0, 0, 0, 10, 32, 42, 128, ..],
     'sleeping_steps': [0, 0, None, None, None, 0, None, ..],
     'active_steps': [None, None, 10, 500, 120242, None, ..],
     'sedentary_steps': [None
    """
    datetimes = []
    totalsteps_list = []
    sleeping_steps_list = []
    active_steps_list = []
    sedentary_steps_list = []
    totalsteps = 0

    for item in content:
        sleeping_steps = 0
        active_steps = 0
        sedentary_steps = 0
        datetimes.append(item['startGMT'])
        totalsteps = totalsteps + item['steps']
        totalsteps_list.append(totalsteps)
        if item['primaryActivityLevel'] == 'sedentary':
            sedentary_steps = item['steps']
        elif item['primaryActivityLevel'] == 'active':
            active_steps = item['steps']
        elif item['primaryActivityLevel'] == 'sleeping':
            sleeping_steps = item['steps']

        sleeping_steps_list.append(sleeping_steps)
        active_steps_list.append(active_steps)
        sedentary_steps_list.append(sedentary_steps)

    return {'datetime': datetimes, 'totalsteps': totalsteps_list,
            'sleeping_steps': sleeping_steps_list, 'active_steps': active_steps_list,
            'sedentary_steps': sedentary_steps_list}


def parse_wellness(content):
    return content


def parse_files(directory, target_directory):
    summary = []
    wellness = []
    for filename in sorted(os.listdir(directory)):
        print filename
        if filename.endswith("_summary.json"):
            # parse summary, create graph
            with open(os.path.join(directory, filename), 'r') as f:
                content = json.load(f)
            summary.append(summary_to_graphdata(content))
        elif filename.endswith(".json"):
            # parse wellness data
            continue
        else:
            continue

    return summary, wellness



def generate_wellnesspage(template_dir, outputfile, summary, wellness):
    """ Generate graphs for the various measurements"""
    loader = jinja2.FileSystemLoader(template_dir)
    environment = jinja2.Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)

    try:
        template = environment.get_template('index.html')
    except jinja2.exceptions.TemplateNotFound as e:
        print 'E Template not found: ' + str(e) + ' in template dir ' + template_dir
        sys.exit(2)

    data = {}
    data['summaries'] = summary
    data['wellness'] = wellness

    output = template.render(data)
    with open(outputfile, 'w') as pf:
        pf.write(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Garmin Data Visualiser',
        epilog = 'Because the hell with APIs!', add_help = 'How to use',
        prog = 'python visualise.py -i <input dir with Wellness json files> -o <output dir>')
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
    outputdir = args['output']
    inputdir = args['input']
    summary, wellness = parse_files(inputdir, outputdir)
    template_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
    print template_dir
    outputfile = os.path.join(outputdir, 'wellness.html')

    # Create output directory (if it does not already exist).
    if not os.path.exists(outputdir):
        os.makedirs(outputdir)

    #generate_wellnesspage(template_dir, outputfile, summary, wellness)

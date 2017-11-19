import argparse
from datetime import datetime
import json
import os
import sys

import jinja2


def unix_to_python(timestamp):
    return datetime.utcfromtimestamp(float(timestamp))


def python_to_string(timestamp, dt_format='%Y-%m-%dT%H:%M:%S.0'):
    """
    Example: 2017-11-11T03:30:00.0
    """
    return datetime.fromtimestamp(int(timestamp)).strftime(dt_format)


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
    highlyactive_steps_list = []
    sedentary_steps_list = []
    generic_steps_list = []
    totalsteps = 0

    for item in content:
        sleeping_steps = 0
        active_steps = 0
        highlyactive_steps = 0
        sedentary_steps = 0
        generic_steps = 0
        datetimes.append(item['startGMT'] + 'Z')
        totalsteps = totalsteps + item['steps']
        totalsteps_list.append(totalsteps)
        if item['primaryActivityLevel'] == 'sedentary':
            sedentary_steps = item['steps']
        elif item['primaryActivityLevel'] == 'active':
            active_steps = item['steps']
        elif item['primaryActivityLevel'] == 'highlyActive':
            highlyactive_steps = item['steps']
        elif item['primaryActivityLevel'] == 'sleeping':
            sleeping_steps = item['steps']
        elif item['primaryActivityLevel'] == 'generic' or item['primaryActivityLevel'] == 'none':
            generic_steps = item['steps']
        else:
            #print(item['primaryActivityLevel'])
            print('Unknown activity level found:')
            print(item)

        sleeping_steps_list.append(sleeping_steps)
        active_steps_list.append(active_steps)
        highlyactive_steps_list.append(highlyactive_steps)
        sedentary_steps_list.append(sedentary_steps)
        generic_steps_list.append(generic_steps)

    return {'datetime': datetimes, 'totalsteps': totalsteps_list,
            'sleeping_steps': sleeping_steps_list, 'active_steps': active_steps_list,
            'highlyactive_steps': highlyactive_steps_list, 'sedentary_steps': sedentary_steps_list,
            'generic_steps': generic_steps_list}


def heartrate_to_graphdata(content):
    values = content['heartRateValues']
    rates = []
    for value in values:
        rates.append([python_to_string(value[0]/1000), value[1]])
    return rates


def stress_to_graphdata(content):
    values = content['stressValuesArray']
    stress = []
    for value in values:
        if value[1] > 0:
            stress.append([python_to_string(value[0]/1000), value[1]])
    return stress


def sleep_to_graphdata(content):
    return {'sleepEndTimestamp': python_to_string(content['dailySleepDTO']['sleepEndTimestampGMT']/1000),
            'sleepStartTimestamp': python_to_string(content['dailySleepDTO']['sleepStartTimestampGMT']/1000),
           }


def parse_wellness(wellness, content):
    try:
        content['allMetrics']
    except TypeError:
        # Not a correct wellness file
        return wellness

    for item in content['allMetrics']['metricsMap']:
        if 'SLEEP_' in item:
            key = item[len('SLEEP_'):].lower()
        else:
            key = item.lstrip('WELLNESS_').lower()
        for value in content['allMetrics']['metricsMap'][item]:
            if key not in wellness:
                wellness[key] = {}
            if value['value']:
                wellness[key][value['calendarDate']] = int(value['value'])
            else:
                wellness[key][value['calendarDate']] = None
    return wellness


def parse_files(directory, target_directory):
    heartrate = {}
    stress = {}
    sleep = {}
    summary = []
    wellness = {}
    for filename in sorted(os.listdir(directory)):
        if filename.endswith("_summary.json"):
            # parse summary, create graph
            with open(os.path.join(directory, filename), 'r') as f:
                content = json.load(f)
            summary.append((filename.split('_')[0], summary_to_graphdata(content)))
        elif filename.endswith("_heartrate.json"):
            # parse heartrate, create graph
            with open(os.path.join(directory, filename), 'r') as f:
                content = json.load(f)
            heartrate[filename.split('_')[0]] = heartrate_to_graphdata(content)
        elif filename.endswith("_stress.json"):
            # parse stress, create graph
            with open(os.path.join(directory, filename), 'r') as f:
                content = json.load(f)
            stress[filename.split('_')[0]] = stress_to_graphdata(content)
        elif filename.endswith("_sleep.json"):
            # parse stress, create graph
            with open(os.path.join(directory, filename), 'r') as f:
                content = json.load(f)
            sleep[filename.split('_')[0]] = sleep_to_graphdata(content)
        elif filename.endswith(".json"):
            # parse wellness data
            with open(os.path.join(directory, filename), 'r') as f:
                content = json.load(f)
            wellness = parse_wellness(wellness, content)
        else:
            continue

    # Reverse list so latest days are on top
    summary = summary[::-1]

    return {'summaries': summary, 'wellness': wellness, 'heartrate': heartrate, 'stress': stress, 'sleep': sleep}


def generate_wellnesspage(template_dir, outputfile, alldata):
    """ Generate graphs for the various measurements"""
    loader = jinja2.FileSystemLoader(template_dir)
    environment = jinja2.Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)

    try:
        template = environment.get_template('wellness.html')
    except jinja2.exceptions.TemplateNotFound as e:
        print 'E Template not found: ' + str(e) + ' in template dir ' + template_dir
        sys.exit(2)

    output = template.render(alldata)
    with open(outputfile, 'w') as pf:
        pf.write(output)


def generate_dailystats(template_dir, outputdir, alldata):
    """ Generate graphs for the various measurements """
    loader = jinja2.FileSystemLoader(template_dir)
    environment = jinja2.Environment(loader=loader, trim_blocks=True, lstrip_blocks=True)

    try:
        template = environment.get_template('dailystats.html')
    except jinja2.exceptions.TemplateNotFound as e:
        print 'E Template not found: ' + str(e) + ' in template dir ' + template_dir
        sys.exit(2)

    for datestamp, summary in alldata['summaries']:
        outputfile = os.path.join(outputdir, datestamp + '.html')
        thisdate = datetime.strptime(datestamp, '%Y-%m-%d')
        alldata['datedayofweek'] = thisdate.strftime('%A')  # Day of week, e.g., Sunday, Monday...
        alldata['datestamp'] = datestamp
        alldata['summary'] = summary
        output = template.render(alldata)
        with open(outputfile, 'w') as pf:
            pf.write(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Garmin Data Visualiser',
                                     epilog='Because the hell with APIs!', add_help='How to use',
                                     prog='python visualise.py -i <input dir with Wellness json files> -o <output dir>')
    parser.add_argument('-i', '--input', required=False,
                        help='Input directory.', default=os.path.join(os.getcwd(), 'Wellness/'))
    parser.add_argument('-o', '--output', required=False,
                        help='Output directory.', default=os.path.join(os.getcwd(), 'Graphs/'))
    args = vars(parser.parse_args())

    # Sanity check, before we do anything:
    if args['input'] is None and args['output'] is None:
        print("Must specify an input (-i) directory for the Wellness data, and an output (-o) directory for graphs.")
        sys.exit()

    # Try to use the user argument from command line
    outputdir = args['output']
    inputdir = args['input']
    alldata = parse_files(inputdir, outputdir)
    template_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
    #outputfile = os.path.join(outputdir, 'wellness.html')

    # Create output directory (if it does not already exist).
    if not os.path.exists(outputdir):
        os.makedirs(outputdir)

    #generate_wellnesspage(template_dir, outputfile, alldata)
    generate_dailystats(template_dir, outputdir, alldata)

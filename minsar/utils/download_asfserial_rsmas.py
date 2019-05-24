#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import time
from minsar.objects.dataset_template import Template
from minsar.objects.rsmas_logging import RsmasLogger, loglevel
from minsar.objects import message_rsmas
from minsar.utils import process_utilities as putils
import minsar.job_submission as js
import glob
from minsar.objects.auto_defaults import PathFind
import password_config as password

logfile_name = os.getenv('OPERATIONS') + '/LOGS/asfserial_rsmas.log'
logger = RsmasLogger(file_name=logfile_name)

inps = None


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('template', metavar="FILE", help='template file to use.')
    parser.add_argument('--submit', dest='submit_flag', action='store_true', help='submits job')

    return parser


def command_line_parse(args):
    global inps

    parser = create_parser()
    inps = parser.parse_args(args)


def generate_files_csv():
    """ Generates a csv file of the files to download serially.
    Uses the `awk` command to generate a csv file containing the data files to be download
    serially. The output csv file is then sent through the `sed` command to remove the first five
    empty values to eliminate errors in download_ASF_serial.py.
    """

    dataset_template = Template(inps.template)
    dataset_template.options.update(PathFind.correct_for_ssara_date_format(dataset_template.options))
    ssaraopt = dataset_template.generate_ssaraopt_string()
    ssaraopt = ssaraopt.split(' ')
    filecsv_options = ['ssara_federated_query.py'] + ssaraopt + ['--print', '|', 'awk',
                                                                 "'BEGIN{FS=\",\"; ORS=\",\"}{ print $14}'", '>',
                                                                 'files.csv']
    csv_command = ' '.join(filecsv_options)
    subprocess.Popen(csv_command, shell=True).wait()
    sed_command = "sed 's/^.\{5\}//' files.csv > new_files.csv"
    subprocess.Popen(sed_command, shell=True).wait()


def run_download_asf_serial(run_number=1):
    """ Runs download_ASF_serial.py with proper files.
    Runs adapted download_ASF_serial.py with a CLI username and password and a csv file containing
    the the files needed to be downloaded (provided by ssara_federated_query.py --print)
    """

    logger.log(loglevel.INFO, "RUN NUMBER: %s", str(run_number))
    if run_number > 10:
        return 0

    asfserial_process = subprocess.Popen(
        ['download_ASF_serial.py', '-username', password.asfuser, '-password', password.asfpass, 'new_files.csv'])

    completion_status = asfserial_process.poll()  # the completion status of the process
    hang_status = False  # whether or not the download has hung
    wait_time = 6  # wait time in 'minutes' to determine hang status
    prev_size = -1  # initial download directory size
    i = 0  # the iteration number (for logging only)

    # while the process has not completed
    while completion_status is None:

        i = i + 1

        # Computer the current download directory size
        curr_size = int(subprocess.check_output(['du', '-s', os.getcwd()]).split()[0].decode('utf-8'))

        # Compare the current and previous directory sizes to determine determine hang status
        if prev_size == curr_size:
            hang_status = True
            logger.log(loglevel.WARNING, "SSARA Hung")
            asfserial_process.terminate()  # teminate the process beacause download hung
            break  # break the completion loop

        time.sleep(60 * wait_time)  # wait 'wait_time' minutes before continuing
        prev_size = curr_size
        completion_status = asfserial_process.poll()
        logger.log(loglevel.INFO,
                   "{} minutes: {:.1f}GB, completion_status {}".format(i * wait_time, curr_size / 1024 / 1024,
                                                                       completion_status))

    exit_code = completion_status  # get the exit code of the command
    logger.log(loglevel.INFO, "EXIT CODE: %s", str(exit_code))

    bad_codes = [137, -9]

    # If the exit code is one that signifies an error, rerun the entire command
    if exit_code in bad_codes or hang_status:
        logger.log(loglevel.WARNING, "Something went wrong, running again")
        run_download_asf_serial(run_number=run_number + 1)

    return exit_code


def change_file_permissions():
    """ changes the permissions of downloaded files to 755 """

    zip_files = glob.glob('S1*.zip')
    for file in zip_files:
        os.chmod(file, 0o666)


if __name__ == "__main__":

    command_line_parse(sys.argv[1:])
    inps.project_name = putils.get_project_name(custom_template_file=inps.template)
    inps.work_dir = putils.get_work_directory(None, inps.project_name)
    inps.slcDir = inps.work_dir + "/SLC"

    #########################################
    # Submit job
    #########################################
    if inps.submit_flag:
        job_file_name = 'download_asfserial_rsmas'
        job_name = inps.template.split(os.sep)[-1].split('.')[0]
        work_dir = inps.work_dir
        wall_time = '24:00'

        js.submit_script(job_name, job_file_name, sys.argv[:], work_dir, wall_time)

    os.chdir(inps.work_dir)
    message_rsmas.log(os.path.basename(sys.argv[0]) + ' ' + ' '.join(sys.argv[1::]))
    os.chdir(inps.slcDir)
    try:
        os.remove(os.path.expanduser('~') + '/.bulk_download_cookiejar.txt')
    except OSError:
        pass

    generate_files_csv()
    succesful = run_download_asf_serial()
    change_file_permissions()
    logger.log(loglevel.INFO, "SUCCESS: %s", str(succesful))
    logger.log(loglevel.INFO, "------------------------------------")

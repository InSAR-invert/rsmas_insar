#!/usr/bin/env python3
########################
# Author: Sara Mirzaee
#######################

import os
import sys
import glob
import time
from minsar.objects import message_rsmas
from minsar.objects.auto_defaults import PathFind
from minsar.utils.stack_run import CreateRun
import minsar.utils.process_utilities as putils
from minsar.job_submission import JOB_SUBMIT

pathObj = PathFind()

###########################################################################################


def main(iargs=None):

    inps = putils.cmd_line_parse(iargs)

    if not iargs is None:
        input_arguments = iargs
    else:
        input_arguments = sys.argv[1::]

    message_rsmas.log(inps.work_dir, os.path.basename(__file__) + ' ' + ' '.join(input_arguments))

    os.chdir(inps.work_dir)

    time.sleep(putils.pause_seconds(inps.wait_time))

    #########################################
    # Submit job
    #########################################

    if inps.submit_flag:
        job_obj = JOB_SUBMIT(inps)
        job_name = 'create_runfiles'
        job_file_name = job_name
        if '--submit' in input_arguments:
            input_arguments.remove('--submit')
        command = [os.path.abspath(__file__)] + input_arguments
        job_obj.submit_script(job_name, job_file_name, command)
        sys.exit(0)

    try:
        dem_file = glob.glob('DEM/*.wgs84')[0]
        inps.template['topsStack.demDir'] = dem_file
    except:
        raise SystemExit('DEM does not exist')
    
    # check for orbits
    orbit_dir = os.getenv('SENTINEL_ORBITS')

    # make run file
    inps.topsStack_template = pathObj.correct_for_isce_naming_convention(inps)
    runObj = CreateRun(inps)
    runObj.run_stack_workflow()

    run_file_list = putils.make_run_list(inps.work_dir)

    with open(inps.work_dir + '/run_files_list', 'w') as run_file:
        for item in run_file_list:
            run_file.writelines(item + '\n')

    local_orbit = os.path.join(inps.work_dir, 'orbits')
    precise_orbits_in_local = glob.glob(local_orbit + '/*/*POEORB*')
    if len(precise_orbits_in_local) > 0:
        for orbit_file in precise_orbits_in_local:
            os.system('cp {} {}'.format(orbit_file, orbit_dir))

    return None

###########################################################################################


if __name__ == "__main__":
    main()

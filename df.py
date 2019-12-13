#!/usr/bin/env python2
import os
import sys
import argparse
import json
import collections
import docker
from helpers_docker import run_docker_compose, anonymize_db
from helpers_docker import sql_export_csv, anonymize_csv_wrapper
from helpers_imaging import split_subjectcode
from logger import LOGGER

DbConfig = collections.namedtuple('DbConfig',
                                  'container, port, user, pwd')
CsvStrategy = collections.namedtuple('CsvStrategy',
                                     'sql_folder, sql_file, csv_name')

def main():
    # GET DATAFACTORY CONFIGURATION
    with open('config.json') as json_data_file:
        config = json.load(json_data_file)

    # EHR folders
    ehr_source_root = os.path.abspath(config['mipmap']['input_folders']['ehr'])
    dbprop_folder = os.path.abspath(config['mipmap']['dbproperties'])
    output_root = os.path.abspath(config['flattening']['output_folder'])
    preprocess_root = os.path.abspath(config['mipmap']['preprocess']['root'])
    capture_root = os.path.abspath(config['mipmap']['capture']['root'])
    harmonize_root = os.path.abspath(config['mipmap']['harmonize']['root'])
    sql_folder = os.path.abspath(config['sql_scripts_folder'])
    # EXPORT STRATEGIES
    strategies = list(config['flattening']['strategy'].keys())
    # IMAGING etl folders (output of imaging pipeline)
    imaging_source_root = os.path.abspath(config['mipmap']['input_folders']['imaging'])
    imaging_mapping_root = os.path.abspath(config['mipmap']['imaging']['root'])
    # ANONYMIZATION
    anonym_output_root = os.path.abspath(config['anonymization']['output_folder'])
    # POSTGRES DOCKER CONTAINER
    container_name = config['db_docker']['container_name']
    client = docker.from_env(timeout=10800)
    try:
        pg_container = client.containers.get(container_name)
        LOGGER.info('Found postgres container named %s' % container_name)
    except:
        LOGGER.warning('Unable to find db container %s' % container_name)
        exit()

    # docker db credentials 
    dbconfig = DbConfig(pg_container,
                        config['db_docker']['postgres_port'],
                        config['db_docker']['postgres_user'],
                        config['db_docker']['postgres_pwd'])

    parser = argparse.ArgumentParser(description='EHR datafactory cli')
    parser.add_argument('step', choices=['preprocess', 'capture',
                                         'harmonize', 'export',
                                         'imaging', 'anonymize',
                                         'mri'
                                         ],
                        help='select datafactory step')
    parser.add_argument('-t', '--type', choices=['nifti', 'dicom'],
                        help='type of mri input files for nmm mri pipeline')
    parser.add_argument('-m', '--mode', choices=['csv', 'db'],
                        help='anonymization file method')
    parser.add_argument('-s', '--source', type=str,
                        help='input folder for ehr csv file')
    parser.add_argument('-c', '--config', type=str,
                        help='folder containing step\'s configuration files')
    parser.add_argument('-o', '--output', type=str,
                        help='DF output folder for the flat csv')
    parser.add_argument('-d', '--dataset', type=str,
                        help='value for the Dataset column in export csv')
    parser.add_argument('--strategy', choices=strategies)

    parser.add_argument('--csv_name', type=str,
                        help='the final flattened csv name')

    parser.add_argument('--csv_anon', type=str,
                        help='input csv file to be anonymized')

    args = parser.parse_args(sys.argv[1:])

    # ----EHR MAPPING TASKS ----
    if args.step == 'preprocess':
        source_folder = os.path.join(ehr_source_root, args.source)
        config_folder = os.path.join(preprocess_root, args.config)
        run_docker_compose(source_folder, config_folder, dbprop_folder)
    elif args.step == 'capture':
        source_folder = os.path.join(ehr_source_root, args.source)
        config_folder = os.path.join(capture_root, args.config)
        run_docker_compose(source_folder, config_folder, dbprop_folder)
    elif args.step == 'harmonize':
        source_folder = ehr_source_root
        config_folder = os.path.join(harmonize_root, args.config)
        run_docker_compose(source_folder, config_folder, dbprop_folder)

    # ----IMAGING CAPTURE MAPPING ----
    elif args.step == 'imaging':
        source_folder = os.path.join(imaging_source_root, args.source)
        config_folder = imaging_mapping_root
        # process the volume.csv and split the subjectcode column into 
        # PATIENT_ID and VISIT_ID columns, creates the volume_df.csv 
        vfilename = config['mipmap']['imaging']['mapping']['input_files'][0]
        pfilename = config['mipmap']['imaging']['mapping']['processed_files'][0]
        inputpath = os.path.join(source_folder, vfilename)
        outputpath = os.path.join(source_folder, pfilename)
        LOGGER.info('Spliting \"subjectcode\" column to \"PATIENT_ID\" & \"VISIT_ID\"')
        split_subjectcode(inputpath, outputpath)
        LOGGER.info('New file stored in %s' % outputpath)
        run_docker_compose(source_folder, config_folder, dbprop_folder)

    # ----ANONIMIZATION PROCESS----
    elif args.step == 'anonymize':
        output_folder = os.path.join(anonym_output_root, args.output)
        # ---i2b2 database anonymization---
        if args.mode == 'db':
            LOGGER.info('i2b2 db anonymization mode')
            anonym_sql = config['anonymization']['anonymization_sql']
            i2b2_anonym = config['db_docker']['anonymized_db']
            i2b2_harm = config['db_docker']['harmonize_db']
            pivoting_sql = config['anonymization']['strategy'][args.strategy]['sql']
            flat_csv_name = config['anonymization']['strategy'][args.strategy]['csv']

            csv_strategy = CsvStrategy(sql_folder, pivoting_sql, flat_csv_name)

            anonymize_db(i2b2_harm, anonym_sql,
                         output_folder, csv_strategy,
                         i2b2_anonym, dbconfig, args.dataset)
            if args.csv_name:
                default_name = os.path.join(output_folder, csv_strategy.csv_name)
                new_name = os.path.join(output_folder, args.csv_name)
                os.rename(default_name, new_name)
                LOGGER.info('Anonymized csv %s created in: %s' % (args.csv_name,
                                                                  output_folder))
            LOGGER.info('Anonymized csv %s created in: %s' % (flat_csv_name,
                                                              output_folder))


            

        # ---csv anonimyzation---
        elif args.mode == 'csv':
            LOGGER.info('csv anonymization mode')
            
            source_path = os.path.join(output_root, args.source, args.csv_anon)
            anonymize_csv_wrapper(source_path, output_folder,
                                  args.csv_name, args.dataset)
            LOGGER.info('Anonymized csv %s created in: %s' % (args.csv_name,
                                                                  output_folder))
        else:
            LOGGER.warning('Please define anonymization mode, see -m keyword')

    # ----CSV FLATTENING ----
    elif args.step == 'export':
        flat_csv_name = config['flattening']['strategy'][args.strategy]['csv']
        pivoting_sql = config['flattening']['strategy'][args.strategy]['sql']
        csv_strategy = CsvStrategy(sql_folder, pivoting_sql, flat_csv_name)
        LOGGER.info('Selected flattening strategy: %s' % args.strategy)
        output_folder = os.path.join(output_root, args.output)
        dataset = args.dataset
        i2b2_harm = config['db_docker']['harmonize_db']
        sql_export_csv(output_folder, csv_strategy,
                       i2b2_harm, dbconfig, dataset)
        if args.csv_name:
            default_name = os.path.join(output_folder, csv_strategy.csv_name)
            new_name = os.path.join(output_folder, args.csv_name)
            os.rename(default_name, new_name)
            LOGGER.info('Flat csv %s created in: %s' % (args.csv_name,
                                                        output_folder))
        LOGGER.info('Flat csv %s created in: %s' % (flat_csv_name,
                                                    output_folder))


    # ----MRI PIPELINE ----
    elif args.step == 'mri':
        script_parallel_path = os.path.abspath('./mri_run_parallel')
        script_merge_path = os.path.abspath('./mri_output_merge')
        mri_raw_root = config['mri']['input_folders']['nifti']['raw']
        mri_raw_folder = os.path.join(mri_raw_root, args.source)
        mri_input_root = config['mri']['input_folders']['nifti']['root']
        mri_input_folder = os.path.join(mri_input_root, args.source)
        # Reorganize mri files
        LOGGER.info('Reorganizing nifti files in folder %s' % mri_input_folder)
        run_cmd = 'python2 mri_nifti_reorganize/organizer.py %s %s' % (mri_raw_folder, mri_input_folder)
        os.system(run_cmd)
        # run matlab spm12 script
        mri_output_spm12_root = config['mri']['output_folders']['spm12']
        mri_output_spm12_folder = os.path.join(mri_output_spm12_root, args.source)
        LOGGER.info('Running spm12 pipeline...')
        LOGGER.info('Storing output files in %s' % mri_output_spm12_folder)
        os.chdir(script_parallel_path)
        run_cmd = 'python2 mri_parallel_preprocessing.py %s %s' % (mri_input_folder, mri_output_spm12_folder)
        LOGGER.info('Executing...%s' % run_cmd)
        os.system(run_cmd)
        # merge the output into one csv
        os.chdir(script_merge_path)
        imaging_source_path = os.path.join(imaging_source_root, args.source)
        run_cmd = 'python2 merge.py %s %s' % (mri_output_spm12_folder, imaging_source_path)
        LOGGER.info('Merging spm12 output pipeline into single csv file in folder %s' % imaging_source_path)
        os.system(run_cmd)


if __name__ == '__main__':
    main()

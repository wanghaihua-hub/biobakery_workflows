#!/usr/bin/env python

"""
bioBakery Workflows: stats visualization workflow

Copyright (c) 2019 Harvard School of Public Health

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
import os
import sys
import re

# import the workflow class from anadama2
from anadama2 import Workflow

# import the document templates and utilities from biobakery_workflows
from biobakery_workflows import utilities

# import the task to convert from biom to tsv
from biobakery_workflows.tasks.sixteen_s import convert_from_biom_to_tsv_list

# import the files for descriptions and paths
from biobakery_workflows import files

# create a workflow instance, providing the version number and description
workflow = Workflow(version="0.1", remove_options=["input"],
                    description="A workflow for stats on wmgx and 16s data sets")

# add the custom arguments to the workflow                          
workflow.add_argument("input",desc="the folder containing taxonomy and functional data files",required=True)

# add the custom arguments to the workflow
workflow.add_argument("project-name",desc="the name of the project", required=True)
workflow.add_argument("metadata-type",desc="the metadata type", required=True, choices=["univariate", "multivariate", "longitudinal"])
workflow.add_argument("covariate-equation",desc="the covariate equation for multivariate studies", default="")
workflow.add_argument("input-metadata",desc="the metadata file (samples as columns or rows)", required=True)
workflow.add_argument("transform",desc="the transform to apply to the data with MaAsLin2 (default is the MaAsLin2 default transform)", default="")
workflow.add_argument("fixed-effects",desc="the fixed effects to apply to the data with MaAsLin2", default="")
workflow.add_argument("random-effects",desc="the random effects to apply to the data with MaAsLin2", default="")
workflow.add_argument("bypass-maaslin",desc="bypass running MaAsLiN", action="store_true")
workflow.add_argument("permutations",desc="the total number of permutations to apply to the permanova", default="4999")
workflow.add_argument("individual-covariates",desc="the covariates, comma-delimited, that do not change per individual (to permutate within in permanova)", default="")
workflow.add_argument("scale",desc="the scale to apply with the permanova", default="100")
workflow.add_argument("min-abundance",desc="the min abundance to apply for filtering", default="0.0001")
workflow.add_argument("min-prevalence",desc="the min prevalence to apply for filtering", default="0.1")
workflow.add_argument("max-missing",desc="the max percentage of missing values for a metadata to not be filtered", default="20.0")
workflow.add_argument("format",desc="the format for the report", default="pdf", choices=["pdf","html"])
workflow.add_argument("top-pathways",desc="the top N significant pathways to plot stratified abundance", default=3)
workflow.add_argument("metadata-categorical",desc="the categorical features (for the plot stratified pathways)", action="append", default=[])
workflow.add_argument("metadata-continuous",desc="the continuous features (for the plot stratified pathways)", action="append", default=[])
workflow.add_argument("metadata-exclude",desc="the features to exclude (for the plot stratified pathways)", action="append", default=[])
workflow.add_argument("introduction-text",desc="the text to include in the intro of the report",
    default="The data was run through the standard stats workflow.")

# get the arguments from the command line
args = workflow.parse_args()

# get the paths for the required files from the set of all input files
data_files=utilities.identify_data_files(args.input)

if len(data_files.keys()) < 1:
    sys.exit("ERROR: No data files found in the input folder.")

study_type=utilities.get_study_type(data_files)

# get inputs based on study type
taxonomic_profile,pathabundance,ecabundance=utilities.get_input_files_for_study_type(data_files,study_type)

# check for any biom files that need to be converted to txt
taxonomic_profile,pathabundance,ecabundance=convert_from_biom_to_tsv_list(workflow,[taxonomic_profile,pathabundance,ecabundance],args.output)

# create feature table files for all input files (for input to maaslin2 and other downstream stats)
maaslin_tasks_info=utilities.create_masslin_feature_table_inputs(workflow,study_type,args.output,taxonomic_profile,pathabundance,ecabundance)

# run MaAsLiN2 on all input files
maaslin_tasks=[]
if not args.bypass_maaslin:
    maaslin_tasks=utilities.run_masslin_on_input_file_set(workflow,maaslin_tasks_info,args.input_metadata,args.transform,args.fixed_effects,args.random_effects)

# generate stratified pathways plots if pathways are provided
stratified_plots_tasks=[]
stratified_pathways_plots=[]
if not args.bypass_maaslin:
    stratified_pathways_plots,stratified_plots_tasks=utilities.create_stratified_pathways_plots(workflow,study_type,pathabundance,args.input_metadata,args.metadata_exclude,args.metadata_categorical,args.metadata_continuous,args.top_pathways,maaslin_tasks_info,args.output)

# run permanova on taxon data if longitudinal else run univariate
additional_stats_tasks=[]
additional_stats_tasks,taxon_permanova=utilities.run_permanova(workflow,args.metadata_type,args.individual_covariates,maaslin_tasks_info,args.input_metadata,args.scale,args.min_abundance,args.min_prevalence,args.permutations,args.output,additional_stats_tasks)

additional_stats_tasks,beta_diversity_plots=utilities.run_beta_diversity(workflow,args.metadata_type,maaslin_tasks_info,args.input_metadata,args.min_abundance,args.min_prevalence,args.max_missing,args.covariate_equation,args.output,additional_stats_tasks)

templates=[utilities.get_package_file("header"),utilities.get_package_file("stats")]

# add the document to the workflow
doc_task=workflow.add_document(
    templates=templates,
    depends=maaslin_tasks+stratified_plots_tasks+[taxonomic_profile]+additional_stats_tasks, 
    targets=workflow.name_output_files("stats_report."+args.format),
    vars={"title":"Stats Report",
          "project":args.project_name,
          "introduction_text":args.introduction_text,
          "taxonomic_profile":taxonomic_profile,
          "maaslin_tasks_info":maaslin_tasks_info,
          "bypass_maaslin":args.bypass_maaslin,
          "stratified_pathways_plots":stratified_pathways_plots,
          "taxon_permanova":taxon_permanova,
          "beta_diversity_plots":beta_diversity_plots,
          "covariate_equation":args.covariate_equation,
          "format":args.format},
    table_of_contents=True)

# add an archive of the document and figures, removing the log file
# the archive will have the same name and location as the output folder
workflow.add_archive(
    depends=[args.output,doc_task],
    targets=args.output+".zip",
    remove_log=True)

# start the workflow
workflow.go()
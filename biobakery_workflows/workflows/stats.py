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
workflow.add_argument("metadata-type",desc="the metadata type", required=True, choices=["univariate", "multi-variate", "longitudinal"])
workflow.add_argument("input-metadata",desc="the metadata file (samples as columns or rows)", required=True)
workflow.add_argument("transform",desc="the transform to apply to the data with MaAsLin2 (default is the MaAsLin2 default transform)", default="")
workflow.add_argument("fixed-effects",desc="the fixed effects to apply to the data with MaAsLin2", default="")
workflow.add_argument("random-effects",desc="the random effects to apply to the data with MaAsLin2", default="")
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

maaslin_optional_args=""
if args.transform:
    maaslin_optional_args+=",transform='"+args.transform+"'"
if args.fixed_effects:
    maaslin_optional_args+=",fixed_effects='"+args.fixed_effects+"'"
if args.random_effects:
    maaslin_optional_args+=",random_effects='"+args.random_effects+"'"

for run_type, (maaslin_input_file, maaslin_heatmap, maaslin_results_table) in maaslin_tasks_info.items():
    maaslin_tasks.append(
        workflow.add_task(
            "R -e \"library('Maaslin2'); results <- Maaslin2('[depends[0]]','[depends[1]]','[args[0]]'"+maaslin_optional_args+")\"",
            depends=[maaslin_input_file, args.input_metadata],
            targets=maaslin_results_table,
            args=os.path.dirname(maaslin_results_table),
            name="R_Maaslin2_{}".format(run_type)))

stratified_pathways_plots = []
stratified_plots_tasks = []
if pathabundance and study_type=="wmgx":
    # read in the metadata to merge with the data for the barplot script
    metadata=utilities.read_metadata(args.input_metadata, pathabundance,
        name_addition="_Abundance", ignore_features=args.metadata_exclude)
    metadata_labels, metadata=utilities.label_metadata(metadata, categorical=args.metadata_categorical, continuous=args.metadata_continuous)
    # get all continuous or samples ids and remove (as they are not to be used for the plots)
    metadata_exclude=args.metadata_exclude+[x for x,y in filter(lambda x: x[1] == "con", metadata_labels.items())]
    for metadata_row in metadata[1:]:
        if len(list(set(metadata_row[1:]))) > utilities.MAX_METADATA_CATEGORIES:
            metadata_exclude+=[metadata_row[0]]
    metadata_exclude=list(set(metadata_exclude))
    metadata=utilities.read_metadata(args.input_metadata, pathabundance,
        name_addition="_Abundance", ignore_features=metadata_exclude)
    metadata_labels, metadata=utilities.label_metadata(metadata, categorical=args.metadata_categorical, continuous=args.metadata_continuous)

    humann2_barplot_input = utilities.name_files("merged_data_metadata_input.tsv", args.output, subfolder="stratified_pathways", create_folder=True)
    workflow.add_task(
        utilities.partial_function(utilities.create_merged_data_file, metadata=metadata),
        depends=pathabundance,
        targets=humann2_barplot_input)

    metadata_row_names=[row[0] for row in metadata[1:]]
    metadata_end=metadata_row_names[-1]
    for i in range(1,args.top_pathways+1):
        for metadata_focus in metadata_row_names:
            if re.match('^[\w-]+$', metadata_focus) is None:
                sys.exit("ERROR: Please modify metadata names to include only alpha-numeric characters: "+metadata_focus)
            new_pathways_plot=utilities.name_files("stratified_pathways_{0}_{1}.jpg".format(metadata_focus,i), args.output, subfolder="stratified_pathways")
            stratified_plots_tasks.append(workflow.add_task(
                utilities.partial_function(utilities.run_humann2_barplot, number=i, metadata_end=metadata_end, metadata_focus=metadata_focus),
                depends=[maaslin_tasks_info["pathways"][2],humann2_barplot_input],
                targets=new_pathways_plot,
                name="run_humann2_barplot_pathway_{0}_{1}".format(i, metadata_focus)))
            stratified_pathways_plots.append(new_pathways_plot)

# run permanova on taxon data if longitudinal
taxon_permanova=None
univariate=None
permanova_task=None
univariate_task=None
additional_depends=[]
if args.metadata_type == "longitudinal":
    taxon_permanova=utilities.name_files("taxon_permanova.png",args.output,subfolder="permanova",create_folder=True)
    permanova_script_path = utilities.get_package_file("permanova_hmp2", "Rscript")
    if args.individual_covariates:
        optional_args=" --individual_covariates "+args.individual_covariates
    else:
        sys.exit("ERROR: Please provide the individual covariates when running with longitudinal metadata (ie --individual-covariates='age,gender')")

    permanova_task = workflow.add_task(
        "[args[0]] [depends[0]] [depends[1]] [targets[0]] --scale [args[1]] --min_abundance [args[2]] --min_prevalence [args[3]] --permutations [args[4]] [args[5]]",
        depends=[maaslin_tasks_info["taxonomy"][0],args.input_metadata],
        targets=taxon_permanova,
        args=[permanova_script_path,args.scale,args.min_abundance,args.min_prevalence,args.permutations,optional_args],
        name="hmp2_permanova")
    additional_depends.append(permanova_task)
else:
    univariate=utilities.name_files("taxon_univariate.png",args.output,subfolder="univariate",create_folder=True)  
    univariate_script_path = utilities.get_package_file("beta_diversity", "Rscript")  

    univariate_task = workflow.add_task(
        "[args[0]] [depends[0]] [depends[1]] [targets[0]] --min_abundance [args[1]] --min_prevalence [args[2]] --max_missing [args[3]]",
        depends=[maaslin_tasks_info["taxonomy"][0],args.input_metadata],
        targets=univariate,
        args=[univariate_script_path,args.min_abundance,args.min_prevalence,args.max_missing],
        name="beta_diversity")
    additional_depends.append(univariate_task)

templates=[utilities.get_package_file("header"),utilities.get_package_file("stats")]

# add the document to the workflow
doc_task=workflow.add_document(
    templates=templates,
    depends=maaslin_tasks+stratified_plots_tasks+[taxonomic_profile]+additional_depends, 
    targets=workflow.name_output_files("stats_report."+args.format),
    vars={"title":"Stats Report",
          "project":args.project_name,
          "introduction_text":args.introduction_text,
          "taxonomic_profile":taxonomic_profile,
          "maaslin_tasks_info":maaslin_tasks_info,
          "stratified_pathways_plots":stratified_pathways_plots,
          "taxon_permanova":taxon_permanova,
          "univariate":univariate,
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

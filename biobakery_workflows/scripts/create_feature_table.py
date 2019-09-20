#!/usr/bin/env python

import sys
import os
import argparse

# This script will take any type of tab-delimited table and reformat it as a feature table
# to be used as input for Maaslin2 and other downstream stats processing.

def parse_arguments(args):
    """ 
    Parse the arguments from the user
    """
    parser = argparse.ArgumentParser(
        description= "Create feature table\n",
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-i", "--input",
        help="the count table\n[REQUIRED]",
        metavar="<input.tsv>",
        required=True)
    parser.add_argument(
        "-o", "--output",
        help="file to write the feature table\n[REQUIRED]",
        metavar="<output>",
        required=True)
    parser.add_argument(
        "--sample-tag-columns",
        help="remove this string from the sample names in columns")

    return parser.parse_args()


def main():

    args=parse_arguments(sys)

    # read in the file and process depending on the arguments provided
    with open(args.input) as file_handle_read:
        with open(args.output,"w") as file_handle_write:
            # remove sample tags from column headers if present
            header = file_handle_read.readline()
            if args.sample_tag_columns:
                header = header.replace(args.sample_tag_columns,"")
            file_handle_write.write(header)

            for line in file_handle_read:
                # ignore and do not write out commented lines
                if not line.startswith("#"):
                    file_handle_write.write(line)
        
if __name__ == "__main__":
    main()



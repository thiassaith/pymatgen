#!/usr/bin/env python
# coding: utf-8
# Copyright (c) Pymatgen Development Team.
# Distributed under the terms of the MIT License.

from __future__ import division, unicode_literals
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve

from tabulate import tabulate_formats

from monty.serialization import loadfn, dumpfn
from pymatgen import SETTINGS_FILE
from pymatgen.io.vasp import Poscar
from pymatgen.io.cif import CifParser, CifWriter
from pymatgen.io.vasp.sets import MPRelaxSet, MITRelaxSet
from pymatgen.io.cssr import Cssr
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.alchemy.materials import TransformedStructure
from pymatgen.cli.pmg_analyze import *
from pymatgen.cli.pmg_setup import *
from pymatgen.cli.pmg_generate_potcar import *
from pymatgen.cli.pmg_plot import *


"""
A master convenience script with many tools for vasp and structure analysis.
"""

__author__ = "Shyue Ping Ong"
__copyright__ = "Copyright 2012, The Materials Project"
__version__ = "4.0"
__maintainer__ = "Shyue Ping Ong"
__email__ = "ongsp@ucsd.edu"
__date__ = "Aug 13 2016"


SAVE_FILE = "vasp_data.gz"


def configure(args):
    d = {}
    if os.path.exists(args.output_file):
        d = loadfn(args.output_file)
    toks = args.var_spec
    if len(toks) % 2 != 0:
        print("Bad variable specification!")
        sys.exit(-1)
    for i in range(int(len(toks) / 2)):
        d[toks[2 * i]] = toks[2 * i + 1]
    dumpfn(d, args.output_file, default_flow_style=False)


def convert_fmt(args):
    iformat = args.input_format[0]
    oformat = args.output_format[0]
    filename = args.input_filename[0]
    out_filename = args.output_filename[0]

    try:

        if iformat == "POSCAR":
            p = Poscar.from_file(filename)
            structure = p.structure
        elif iformat == "CIF":
            r = CifParser(filename)
            structure = r.get_structures()[0]
        elif iformat == "CONVENTIONAL_CIF":
            r = CifParser(filename)
            structure = r.get_structures(primitive=False)[0]
        elif iformat == "CSSR":
            structure = Cssr.from_file(filename).structure
        else:
            structure = Structure.from_file(filename)

        if oformat == "smart":
            structure.to(filename=out_filename)
        elif oformat == "POSCAR":
            p = Poscar(structure)
            p.write_file(out_filename)
        elif oformat == "CIF":
            w = CifWriter(structure)
            w.write_file(out_filename)
        elif oformat == "CSSR":
            c = Cssr(structure)
            c.write_file(out_filename)
        elif oformat == "VASP":
            ts = TransformedStructure(
                structure, [],
                history=[{"source": "file",
                          "datetime": str(datetime.datetime.now()),
                          "original_file": open(filename).read()}])
            ts.write_vasp_input(MPRelaxSet, output_dir=out_filename)
        elif oformat == "MITVASP":
            ts = TransformedStructure(
                structure, [],
                history=[{"source": "file",
                          "datetime": str(datetime.datetime.now()),
                          "original_file": open(filename).read()}])
            ts.write_vasp_input(MITRelaxSet, output_dir=out_filename)

    except Exception as ex:
        print("Error converting file. Are they in the right format?")
        print(str(ex))


def parse_symmetry(args):

    tolerance = float(args.tolerance[0])

    for filename in args.filenames:
        s = Structure.from_file(filename)
        if args.spacegroup:
            finder = SpacegroupAnalyzer(s, tolerance)
            dataset = finder.get_symmetry_dataset()
            print(filename)
            print("Spacegroup  : {}".format(dataset["international"]))
            print("Int number  : {}".format(dataset["number"]))
            print("Hall symbol : {}".format(dataset["hall"]))
            print("")


def analyze_structure(args):
    bonds = {}
    for bond in args.localenv:
        toks = bond.split("=")
        species = toks[0].split("-")
        bonds[(species[0], species[1])] = float(toks[1])
    for filename in args.filenames:
        print("Analyzing %s..." % filename)
        data = []
        s = Structure.from_file(filename)
        for i, site in enumerate(s):
            for species, dist in bonds.items():
                if species[0] in [sp.symbol
                                  for sp in site.species_and_occu.keys()]:
                    dists = [d for nn, d in s.get_neighbors(site, dist)
                             if species[1] in
                             [sp.symbol for sp in nn.species_and_occu.keys()]]
                    dists = ", ".join(["%.3f" % d for d in sorted(dists)])
                    data.append([i, species[0], species[1], dists])
        print(tabulate(data, headers=["#", "Center", "Ligand", "Dists"]))


def parse_view(args):
    from pymatgen.vis.structure_vtk import StructureVis
    excluded_bonding_elements = args.exclude_bonding[0].split(",") \
        if args.exclude_bonding else []
    s = Structure.from_file(args.filename[0])
    vis = StructureVis(excluded_bonding_elements=excluded_bonding_elements)
    vis.set_structure(s)
    vis.show()


def compare_structures(args):
    filenames = args.filenames
    if len(filenames) < 2:
        print("You need more than one structure to compare!")
        sys.exit(-1)
    try:
        structures = [Structure.from_file(fn) for fn in filenames]
    except Exception as ex:
        print("Error converting file. Are they in the right format?")
        print(str(ex))
        sys.exit(-1)

    from pymatgen.analysis.structure_matcher import StructureMatcher, \
        ElementComparator
    m = StructureMatcher() if args.oxi \
        else StructureMatcher(comparator=ElementComparator())
    for i, grp in enumerate(m.group_structures(structures)):
        print("Group {}: ".format(i))
        for s in grp:
            print("- {} ({})".format(filenames[structures.index(s)],
                                     s.formula))
        print()


def diff_incar(args):
    filepath1 = args.filenames[0]
    filepath2 = args.filenames[1]
    incar1 = Incar.from_file(filepath1)
    incar2 = Incar.from_file(filepath2)

    def format_lists(v):
        if isinstance(v, (tuple, list)):
            return " ".join(["%d*%.2f" % (len(tuple(group)), i)
                             for (i, group) in itertools.groupby(v)])
        return v

    d = incar1.diff(incar2)
    output = [['SAME PARAMS', '', ''], ['---------------', '', ''],
              ['', '', ''], ['DIFFERENT PARAMS', '', ''],
              ['----------------', '', '']]
    output.extend([(k, format_lists(d['Same'][k]), format_lists(d['Same'][k]))
                   for k in sorted(d['Same'].keys()) if k != "SYSTEM"])
    output.extend([(k, format_lists(d['Different'][k]['INCAR1']),
                    format_lists(d['Different'][k]['INCAR2']))
                   for k in sorted(d['Different'].keys()) if k != "SYSTEM"])
    print(tabulate(output, headers=['', filepath1, filepath2]))


def main():
    parser = argparse.ArgumentParser(description="""
    pmg is a convenient script that uses pymatgen to perform many
    analyses, plotting and format conversions. This script works based on
    several sub-commands with their own options. To see the options for the
    sub-commands, type "pmg sub-command -h".""",
                                     epilog="""
    Author: Shyue Ping Ong
    Version: {}
    Last updated: {}""".format(__version__, __date__))

    subparsers = parser.add_subparsers()

    parser_setup = subparsers.add_parser("setup", help="Setup pymatgen.")
    parser_setup.add_argument("-p", "--potcar",
                              dest="potcar_dirs", type=str, nargs=2,
                              help="Initial directory where downloaded VASP "
                                   "POTCARs are extracted to, and the "
                                   "output directory where the reorganized "
                                   "potcars will be stored. The input "
                                   "directory should be "
                                   "the parent directory that contains the "
                                   "POT_GGA_PAW_PBE or potpaw_PBE type "
                                   "subdirectories.")
    parser_setup.add_argument("-i", "--install",
                              dest="install", type=str,
                              choices=["enum", "bader"],
                              help="Install various optional command line "
                                   "tools needed for full functionality.")
    parser_setup.set_defaults(func=setup_pmg)

    parser_config = subparsers.add_parser("config", help="Tools for "
                                                        "configuration file "
                                                        ".pmgrc.yaml")
    parser_config.add_argument("-a", "--add",
                               dest="var_spec", type=str,
                               required=True, nargs="+",
                               help="Variables to add in the form of space "
                                    "separated key value pairs. E.g., "
                                    "VASP_PSP_DIR ~/psps")
    parser_config.add_argument("-o", "--output_file",
                               dest="output_file", type=str,
                               default=SETTINGS_FILE,
                               help="Output file to write the config to. "
                                    "Defaults to standard config file "
                                    "location in ~/.pmgrc.yaml. Use this if "
                                    "you just want to see the file first.")
    parser_config.set_defaults(func=configure)

    parser_vasp = subparsers.add_parser("analyze", help="Vasp run analysis.")
    parser_vasp.add_argument("directories", metavar="dir", default=".",
                             type=str, nargs="*",
                             help="directory to process (default to .)")
    parser_vasp.add_argument("-e", "--energies", dest="get_energies",
                             action="store_true", help="Print energies")
    parser_vasp.add_argument("-m", "--mag", dest="ion_list", type=str, nargs=1,
                             help="Print magmoms. ION LIST can be a range "
                             "(e.g., 1-2) or the string 'All' for all ions.")
    parser_vasp.add_argument("-r", "--reanalyze", dest="reanalyze",
                             action="store_true",
                             help="Force reanalysis. Typically, vasp_analyzer"
                             " will just reuse a vasp_analyzer_data.gz if "
                             "present. This forces the analyzer to reanalyze "
                             "the data.")
    parser_vasp.add_argument("-f", "--format", dest="format",
                             choices=tabulate_formats, default="simple",
                             type=str,
                             help="Format for table. Supports all options in "
                                  "tabulate package.")
    parser_vasp.add_argument("-v", "--verbose", dest="verbose",
                             action="store_true",
                             help="verbose mode. Provides detailed output on "
                             "progress.")
    parser_vasp.add_argument("-d", "--detailed", dest="detailed",
                             action="store_true",
                             help="Detailed mode. Parses vasprun.xml instead "
                             "of separate vasp input. Slower.")
    parser_vasp.add_argument("-s", "--sort", dest="sort", type=str, nargs=1,
                             default=["energy_per_atom"],
                             help="Sort criteria. Defaults to energy / atom.")
    parser_vasp.set_defaults(func=parse_vasp)

    parser_plot = subparsers.add_parser("plot", help="Plotting tool for "
                                                     "DOS, CHGCAR, XRD, etc.")
    group = parser_plot.add_mutually_exclusive_group()
    group.add_argument('-d', '--dos', dest="dos_file",
                       help="Plot DOS from a vasprun.xml")
    group.add_argument('-c', '--chgint', dest="chgcar_file",
                       help="Generate charge integration plots from any "
                            "CHGCAR")
    group.add_argument('-x', '--xrd', dest="xrd_structure_file",
                       help="Generate XRD plots from any structure file")

    parser_plot.add_argument("-s", "--site", dest="site", action="store_const",
                             const=True, help="Plot site projected DOS")
    parser_plot.add_argument("-e", "--element", dest="element", type=str,
                             nargs=1,
                             help="List of elements to plot as comma-separated"
                             " values e.g., Fe,Mn")
    parser_plot.add_argument("-o", "--orbital", dest="orbital",
                             action="store_const", const=True,
                             help="Plot orbital projected DOS")

    parser_plot.add_argument("-i", "--indices", dest="inds", type=str,
                             nargs=1,
                             help="Comma-separated list of indices to plot "
                                  "charge integration, e.g., 1,2,3,4. If not "
                                  "provided, the code will plot the chgint "
                                  "for all symmetrically distinct atoms "
                                  "detected.")
    parser_plot.add_argument("-r", "--radius", dest="radius", type=float,
                             default=3,
                             help="Radius of integration for charge "
                                  "integration plot.")
    parser_plot.add_argument("--out_file", dest="out_file", type=str,
                             help="Save plot to file instead of displaying.")
    parser_plot.set_defaults(func=plot)


    parser_convert = subparsers.add_parser(
        "convert", help="File format conversion tools.")
    parser_convert.add_argument("input_filename", metavar="input_filename",
                                type=str, nargs=1, help="Input filename.")
    parser_convert.add_argument("output_filename", metavar="output_filename",
                                type=str, nargs=1,
                                help="Output filename (for POSCAR/CIF/CSSR "
                                "output) / dirname (VASP output)")
    parser_convert.add_argument("-i", "--input", dest="input_format",
                                type=str.upper,
                                nargs=1,
                                choices=["POSCAR", "CIF", "CSSR", "smart",
                                         "CONVENTIONAL_CIF"],
                                default=["smart"],
                                help="Input file format. By default, smart is "
                                "selected, which guesses the format from the "
                                "filename. Other formats can be enforced as "
                                "needed. If CONVENTIONAL_CIF is chosen instead "
                                "of CIF, no primitive cell reduction is done.")

    parser_convert.add_argument("-o", "--output", dest="output_format",
                                type=str.upper, nargs=1,
                                choices=["POSCAR", "CIF", "CSSR", "VASP",
                                         "MITVASP",
                                         "smart"],
                                default=["smart"],
                                help="Output file format. By default, smart is"
                                " selected, which guesses the format from the "
                                "filename. Other formats can be enforced as "
                                "needed. VASP is a special output form, which "
                                "outputs a set of VASP input files to a "
                                "directory. MITVASP uses the MIT input set "
                                "instead of the default Materials project "
                                "input set.")
    parser_convert.set_defaults(func=convert_fmt)

    parser_symm = subparsers.add_parser("symm", help="Symmetry tools.")
    parser_symm.add_argument("filenames", metavar="filenames", type=str,
                             nargs="+",
                             help="Filenames to determine symmetry.")
    parser_symm.add_argument("-t", "--tolerance", dest="tolerance", type=float,
                             nargs=1, default=[0.1],
                             help="Tolerance for symmetry determination")
    parser_symm.add_argument("-s", "--spacegroup", dest="spacegroup",
                             action="store_true",
                             help="Determine symmetry")
    parser_symm.set_defaults(func=parse_symmetry)

    parser_view = subparsers.add_parser("view", help="Visualize structures")
    parser_view.add_argument("filename", metavar="filename", type=str,
                             nargs=1, help="Filename")
    parser_view.add_argument("-e", "--exclude_bonding", dest="exclude_bonding",
                             type=str, nargs=1,
                             help="List of elements to exclude from bonding "
                             "analysis. E.g., Li,Na")
    parser_view.set_defaults(func=parse_view)

    parser_cmp = subparsers.add_parser("compare", help="Compare structures")
    parser_cmp.add_argument("filenames", metavar="filenames", type=str,
                            nargs="*", help="List of filenames to compare.")
    parser_cmp.add_argument("-o", "--oxi", dest="oxi",
                            action="store_true",
                            help="Oxi mode means that different oxidation "
                                 "states will not match to each other, i.e.,"
                                 " Fe2+ amd Fe3+ will be treated as "
                                 "different species for the purposes of "
                                 "matching.")
    parser_cmp.set_defaults(func=compare_structures)

    parser_diffincar = subparsers.add_parser(
        "diff_incar", help="Helpful diffing tool for INCARs")
    parser_diffincar.add_argument("filenames", metavar="filenames", type=str,
                            nargs=2, help="List of INCARs to compare.")
    parser_diffincar.set_defaults(func=diff_incar)

    parser_potcar = subparsers.add_parser("potcar",
                                            help="Generate POTCARs")
    parser_potcar.add_argument("-f", "--functional", dest="functional",
                                 type=str,
                                 choices=["LDA", "PBE", "PW91", "LDA_US"],
                                 default="PBE",
                                 help="Functional to use. Unless otherwise "
                                      "stated (e.g., US), "
                                      "refers to PAW psuedopotential.")
    parser_potcar.add_argument("-s", "--symbols", dest="symbols",
                                 type=str, nargs="+",
                                 help="List of POTCAR symbols. Use -f to set "
                                      "functional. Defaults to PBE.")
    parser_potcar.add_argument("-r", "--recursive", dest="recursive",
                                 type=str, nargs="+",
                                 help="Dirname to find and generate from POTCAR.spec.")
    parser_potcar.set_defaults(func=generate_potcar)

    parser_structure = subparsers.add_parser(
        "structure",
        help="Structure analysis tools.")
    parser_structure.add_argument(
        "filenames", metavar="filenames", type=str, nargs="+",
        help="List of input structure files to analyze.")
    parser_structure.add_argument(
        "-l", "--localenv", dest="localenv", type=str, nargs="+",
        help="Local environment analysis. Provide bonds in the format of"
             "Center Species-Ligand Species=max_dist, e.g., H-O=0.5.")
    parser_structure.set_defaults(func=analyze_structure)

    args = parser.parse_args()

    try:
        getattr(args, "func")
    except AttributeError:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()
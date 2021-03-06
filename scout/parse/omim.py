import sys
import re
import click
import logging

mimnr_pattern = re.compile("[0-9]{6,6}")
entry_pattern = re.compile("\([1,2,3,4]\)")

mim_inheritance_terms = [
        'Autosomal recessive',
        'Autosomal dominant',
        'X-linked dominant',
        'X-linked recessive',
        'Y-linked',
        'Mitochondrial'
    ]

TERMS_MAPPER = {
     'Autosomal recessive': 'AR',
     'Autosomal dominant': 'AD',
     'X-linked dominant': 'XD',
     'X-linked recessive': 'XR',
     'Y-linked': 'Y',
     'Mitochondrial': 'MT'
   }

log = logging.getLogger(__name__)

def parse_omim_line(line, header):
    """docstring for parse_omim_2_line"""
    omim_info = dict(zip(header, line.split('\t')))
    return omim_info

def parse_genemap2(lines):
    """Parse the omim source file called genemap2.txt
    
    Explanation of Phenotype field:
    Brackets, "[ ]", indicate "nondiseases," mainly genetic variations that 
    lead to apparently abnormal laboratory test values.

    Braces, "{ }", indicate mutations that contribute to susceptibility to 
    multifactorial disorders (e.g., diabetes, asthma) or to susceptibility 
    to infection (e.g., malaria).

    A question mark, "?", before the phenotype name indicates that the 
    relationship between the phenotype and gene is provisional. 
    More details about this relationship are provided in the comment 
    field of the map and in the gene and phenotype OMIM entries.

    The number in parentheses after the name of each disorder indicates 
    the following: 
        (1) the disorder was positioned by mapping of the wildtype gene; 
        (2) the disease phenotype itself was mapped; 
        (3) the molecular basis of the disorder is known; 
        (4) the disorder is a chromosome deletion or duplication syndrome. 
    
    Args:
        lines(iterable(str))
    
    Yields:
        parsed_entry(dict)
    """
    log.info("Parsing the omim genemap2")
    header = []
    for i,line in enumerate(lines):
        line = line.rstrip()
        if line.startswith('#'):
            if i < 10:
                if line.startswith('# Chromosome'):
                    header = line[2:].split('\t')
        else:
            parsed_entry = parse_omim_line(line, header)
            parsed_entry['mim_number'] = int(parsed_entry['Mim Number'])
            # This is the approved symbol for the entry
            hgnc_symbol = parsed_entry.get("Approved Symbol")
            # If no approved symbol could be found choose the first of
            # the gene symbols
            if not hgnc_symbol:
                if parsed_entry.get('Gene Symbols'):
                    hgnc_symbol = parsed_entry['Gene Symbols'].split(',')[0].strip() 
            parsed_entry['hgnc_symbol'] = hgnc_symbol
            # Gene inheritance is a construct. It is the union of all inheritance
            # patterns found in the associated phenotypes
            gene_inheritance = set()
            parsed_phenotypes = []
            # These information about the related phenotypes
            if parsed_entry.get('Phenotypes'):
                # Each related phenotype is separated by ';'
                for phenotype_info in parsed_entry['Phenotypes'].split(';'):
                    phenotype_info = phenotype_info.lstrip()
                    # print(phenotype_info)
                    # Skip phenotype entries that are to uncertain
                    if not phenotype_info.startswith('['):
                        phenotype_status = 'established'
                        # We will try to save the description
                        description = ""
                        if phenotype_info.startswith('{'):
                            phenotype_status = 'susceptibility'
                        if phenotype_info.startswith('?'):
                            phenotype_status = 'provisional'
                        
                        splitted_info = phenotype_info.split(',')
                        for i,text in enumerate(splitted_info):
                            # Everything before ([1,2,3])
                            # We check if we are in the part where the mim number exists
                            match = entry_pattern.search(text)
                            if not match:
                                description += text.strip('?\{\}')
                            else:
                                # If we find the end of the entry
                                mimnr_match = mimnr_pattern.search(phenotype_info)
                                # Then if the entry have a mim number we choose that
                                if mimnr_match:
                                    phenotype_mim = int(mimnr_match.group())
                                else:
                                    phenotype_mim = parsed_entry['mim_number']
                                    description += text[:-4]
                                break
                        # Find the inheritance
                        inheritance = set()
                        inheritance_text = ','.join(splitted_info[i:])
                        for term in mim_inheritance_terms:
                            if term in inheritance_text:
                                
                                inheritance.add(TERMS_MAPPER[term])
                                gene_inheritance.add(TERMS_MAPPER[term])
                        
                        parsed_phenotypes.append(
                                            {
                                                'mim_number':phenotype_mim, 
                                                'inheritance': inheritance,
                                                'description': description,
                                                'status': phenotype_status,
                                            }
                                        )
            
            parsed_entry['phenotypes'] = parsed_phenotypes
            parsed_entry['inheritance'] = gene_inheritance
                    
            yield parsed_entry


def parse_mim2gene(lines):
    """Parse the file called mim2gene
    
    This file describes what type(s) the different mim numbers have.
    The different entry types are: 'gene', 'gene/phenotype', 'moved/removed',
    'phenotype', 'predominantly phenotypes'
    Where:
        gene: Is a gene entry
        gene/phenotype: This entry describes both a phenotype and a gene
        moved/removed: No explanation needed
        phenotype: Describes a phenotype
        predominantly phenotype: Not clearly established (probably phenotype)
    
    Args:
        lines(iterable(str)): The mim2gene lines
    
    Yields:
        parsed_entry(dict)
    
        {
        "mim_number": int, 
        "entry_type": str, 
        "entrez_gene_id": int, 
        "hgnc_symbol": str, 
        "ensembl_gene_id": str,
        "ensembl_transcript_id": str,
        }
    
    """
    log.info("Parsing mim2gene")
    header = ["mim_number", "entry_type", "entrez_gene_id", "hgnc_symbol", "ensembl_gene_id"]
    for i, line in enumerate(lines):
        line = line.rstrip()
        if not line.startswith('#'):
            parsed_entry = parse_omim_line(line, header)
            parsed_entry['mim_number'] = int(parsed_entry['mim_number'])
            
            if 'hgnc_symbol' in parsed_entry:
                parsed_entry['hgnc_symbol'] = parsed_entry['hgnc_symbol']
            
            if parsed_entry.get('entrez_gene_id'):
                parsed_entry['entrez_gene_id'] = int(parsed_entry['entrez_gene_id'])
            
            if parsed_entry.get('ensembl_gene_id'):
                ensembl_info = parsed_entry['ensembl_gene_id'].split(',')
                parsed_entry['ensembl_gene_id'] = ensembl_info[0].strip()
                parsed_entry['ensembl_transcript_id'] = ensembl_info[1].strip()
            
            yield parsed_entry

def parse_omim_morbid(lines):
    """docstring for parse_omim_morbid"""
    header = []
    for i,line in enumerate(lines):
        line = line.rstrip()
        if line.startswith('#'):
            if i < 10:
                if line.startswith('# Phenotype'):
                    header = line[2:].split('\t')
        else:
            yield parse_omim_line(line, header)

def parse_mim_titles(lines):
    """Parse the mimTitles.txt file
    
    This file hold information about the description for each entry in omim.
    There is not information about entry type.
    parse_mim_titles collects the preferred title and maps it to the mim number.
    
    Args:
        lines(iterable): lines from mimTitles file
    
    Yields:
        parsed_entry(dict)
    
        {
        'mim_number': int, # The mim number for entry
        'preferred_title': str, # the preferred title for a entry
        }

    """
    header = ['prefix', 'mim_number', 'preferred_title', 'alternative_title', 'included_title']
    for i,line in enumerate(lines):
        line = line.rstrip()
        if not line.startswith('#'):
            parsed_entry = parse_omim_line(line, header)
            parsed_entry['mim_number'] = int(parsed_entry['mim_number'])
            parsed_entry['preferred_title'] = parsed_entry['preferred_title'].split(';')[0]
            yield parsed_entry

def get_mim_genes(genemap_lines, mim2gene_lines):
    """Get a dictionary with genes and their omim information
    
    Args:
        genemap_lines(iterable(str))
        mim2gene_lines(iterable(str))
    
    Returns.
        hgnc_genes(dict): A dictionary with hgnc_symbol as keys
    
    """
    log.info("Get the mim genes")
    
    genes = {}
    hgnc_genes = {}
    
    gene_nr = 0
    no_hgnc = 0
    
    for entry in parse_mim2gene(mim2gene_lines):
        if 'gene' in entry['entry_type']:
            mim_nr = entry['mim_number']
            gene_nr += 1
            if not 'hgnc_symbol' in entry:
                no_hgnc += 1
            else:
                genes[mim_nr] = entry
    log.info("Numnber of genes without hgnc symbol %s", str(no_hgnc))
    
    for entry in parse_genemap2(genemap_lines):
        mim_number = entry['mim_number']
        inheritance = entry['inheritance']
        phenotype_info = entry['phenotypes']
        hgnc_symbol = entry['hgnc_symbol']
        if mim_number in genes:
            genes[mim_number]['inheritance'] = inheritance
            genes[mim_number]['phenotypes'] = phenotype_info

    for mim_nr in genes:
        gene_info = genes[mim_nr]
        hgnc_symbol = gene_info['hgnc_symbol']
        
        if hgnc_symbol in hgnc_genes:
            existing_info = hgnc_genes[hgnc_symbol]
            if not existing_info['phenotypes']:
                hgnc_genes[hgnc_symbol] = gene_info
            
        else:
            hgnc_genes[hgnc_symbol] = gene_info
    
    return hgnc_genes
    
def get_mim_phenotypes(genemap_lines):
    """Get a dictionary with phenotypes
    
    Use the mim numbers for phenotypes as keys and phenotype information as 
    values.

    Args:
        genemap_lines(iterable(str))
    
    Returns:
        phenotypes_found(dict): A dictionary with mim_numbers as keys and 
        dictionaries with phenotype information as values.
    
        {
             'description': str, # Description of the phenotype
             'hgnc_symbols': set(), # Associated hgnc symbols
             'inheritance': set(),  # Associated phenotypes
             'mim_number': int, # mim number of phenotype
        }
    """
    # Set with all omim numbers that are phenotypes
    # Parsed from mim2gene.txt
    phenotype_mims = set()
    
    phenotypes_found = {}

    # Genemap is a file with one entry per gene.
    # Each line hold a lot of information and in specific it
    # has information about the phenotypes that a gene is associated with
    # From this source we collect inheritane patterns and what hgnc symbols
    # a phenotype is associated with
    for entry in parse_genemap2(genemap_lines):
        hgnc_symbol = entry['hgnc_symbol']
        for phenotype in entry['phenotypes']:
            mim_nr = phenotype['mim_number']
            if mim_nr in phenotypes_found:
                phenotype_entry = phenotypes_found[mim_nr]
                phenotype_entry['inheritance'] = phenotype_entry['inheritance'].union(phenotype['inheritance'])
                phenotype_entry['hgnc_symbols'].add(hgnc_symbol)
            else:
                phenotype['hgnc_symbols'] = set([hgnc_symbol])
                phenotypes_found[mim_nr] = phenotype

    return phenotypes_found
    

@click.command()
@click.option('--morbid', type=click.Path(exists=True))
@click.option('--genemap', type=click.Path(exists=True))
@click.option('--mim2gene', type=click.Path(exists=True))
@click.option('--mim_titles', type=click.Path(exists=True))
@click.option('--phenotypes', is_flag=True)
@click.pass_context
def cli(context, morbid, genemap, mim2gene, mim_titles, phenotypes):
    """Parse the omim files"""
    # if not (morbid and genemap and mim2gene, mim_titles):
    #     print("Please provide all files")
    #     context.abort()

    from scout.utils.handle import get_file_handle
    from pprint import pprint as pp
    
    print("Morbid file: %s" % morbid)
    print("Genemap file: %s" % genemap)
    print("mim2gene file: %s" % mim2gene)
    print("MimTitles file: %s" % mim_titles)
    
    
    if morbid:
        morbid_handle = get_file_handle(morbid)
    if genemap:
        genemap_handle = get_file_handle(genemap)
    if mim2gene:
        mim2gene_handle = get_file_handle(mim2gene)
    if mim_titles:
        mimtitles_handle = get_file_handle(mim_titles)

    
    mim_genes = get_mim_genes(genemap_handle, mim2gene_handle)
    for entry in mim_genes: 
        if entry == 'C10orf11':
            pp(mim_genes[entry])
    
    context.abort()
    if phenotypes:
        if not genemap:
            click.echo("Please provide the genemap file")
            context.abort()
        phenotypes = get_mim_phenotypes(genemap_handle)
        for i,mim_term in enumerate(phenotypes):
            # pp(phenotypes[mim_term])
            pass
    
    print("Number of phenotypes found: %s" % i)
    
    context.abort()
    # hgnc_genes = get_mim_genes(genemap_handle, mim2gene_handle)
    # for hgnc_symbol in hgnc_genes:
    #     pp(hgnc_genes[hgnc_symbol])
    # phenotypes = get_mim_phenotypes(genemap_handle, mim2gene_handle, mimtitles_handle)
    # for mim_nr in phenotypes:
    #     pp(phenotypes[mim_nr])
    
    genes = get_mim_genes(genemap_handle, mim2gene_handle)
    for hgnc_symbol in genes:
        if hgnc_symbol == 'OPA1':
            print(genes[hgnc_symbol])

if __name__ == '__main__':
    cli()
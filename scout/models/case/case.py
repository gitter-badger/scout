from __future__ import (unicode_literals, absolute_import)
from datetime import datetime
import itertools

from mongoengine import (Document, StringField, ListField, ReferenceField,
                         EmbeddedDocumentField, DateTimeField, BooleanField,
                         BinaryField, FloatField, DictField)

from . import STATUS
from .individual import Individual
from .gene_list import GeneList
from scout.models import PhenotypeTerm


class Case(Document):
  """Represents a case (family) of individuals (samples)."""
  # This is a string with the id for the family:
  case_id = StringField(primary_key=True, required=True)
  # This is the string that will be shown in scout:
  display_name = StringField(required=True)
  # This is the owner of the case. E.g. 'cust003'
  owner = StringField(required=True)
  # These are the names of all the collaborators that are allowed to view the
  # case, including the owner
  collaborators = ListField(StringField())
  assignee = ReferenceField('User')
  individuals = ListField(EmbeddedDocumentField(Individual))
  created_at = DateTimeField(default=datetime.now)
  updated_at = DateTimeField(default=datetime.now)
  suspects = ListField(ReferenceField('Variant'))
  causative = ReferenceField('Variant')

  # The synopsis is a text blob
  synopsis = StringField(default='')
  status = StringField(default='inactive', choices=STATUS)
  is_research = BooleanField(default=False)

  # default_gene_lists specifies which gene lists that should be shown when
  # the case is opened
  default_gene_lists = ListField(StringField())
  clinical_gene_lists = ListField(EmbeddedDocumentField(GeneList))
  research_gene_lists = ListField(EmbeddedDocumentField(GeneList))
  dynamic_gene_list = ListField(DictField())

  genome_build = StringField()
  genome_version = FloatField()

  analysis_date = StringField()

  gender_check = StringField(choices=['unconfirmed', 'confirm', 'deviation'],
                             default='unconfirmed')
  phenotype_terms = ListField(EmbeddedDocumentField(PhenotypeTerm))
  # madeline info is a full xml file
  madeline_info = StringField()
  vcf_file = StringField()

  # The coverage report will be read as a binary blob
  coverage_report = BinaryField()

  @property
  def is_solved(self):
      """Check if the case is marked as solved."""
      return self.status == 'solved'

  @property
  def hpo_gene_ids(self):
    """Parse out all HGNC symbols form the dynamic Phenomizer query."""
    return [term['gene_id'] for term in self.dynamic_gene_list if term['gene_id']]

  @property
  def bam_files(self):
    """Aggregate all BAM files across all individuals."""
    return [individual.bam_file for individual in self.individuals
            if individual.bam_file]

  @property
  def all_gene_lists(self):
    """Yield all gene lists (both clinical and research)."""
    return itertools.chain(self.clinical_gene_lists, self.research_gene_lists)

  def __repr__(self):
    return "Case(case_id={0}, display_name={1}, owner={2})".format(
      self.case_id, self.display_name, self.owner)
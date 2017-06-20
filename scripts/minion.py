#Written by Nick Loman (@pathogenomenick)

import os
import sys
from Bio import SeqIO
from clint.textui import colored, puts, indent

def get_nanopolish_header(ref):
	recs = list(SeqIO.parse(open(ref), "fasta"))
	if len (recs) != 1:
		print >>sys.stderr, "FASTA has more than one sequence"
		raise SystemExit

	return  "%s:%d-%d" % (recs[0].id, 1, len(recs[0])+1)

def run(parser, args):
	ref = "%s/%s/V1/%s.reference.fasta" % (args.scheme_directory, args.scheme, args.scheme)
	bed = "%s/%s/V1/%s.scheme.bed" % (args.scheme_directory, args.scheme, args.scheme)

	if not os.path.exists(ref):
		print colored.red('Scheme reference file not found: ') + ref
		raise SystemExit
	if not os.path.exists(bed):
		print colored.red('Scheme BED file not found: ') + bed
		raise SystemExit

	cmds = []

	nanopolish_header = get_nanopolish_header(ref)

	# 3) index the ref & align with bwa"
	cmds.append("bwa index %s" % (ref,))
	cmds.append("bwa mem -t %s -x ont2d %s %s.fasta | samtools view -bS - | samtools sort -o %s.sorted.bam -" % (args.threads, ref, args.sample, args.sample))
	cmds.append("samtools index %s.sorted.bam" % (args.sample,))

	# 4) trim the alignments to the primer start sites and normalise the coverage to save time
	cmds.append("align_trim.py --start --normalise 100 %s --report %s.alignreport.txt < %s.sorted.bam 2> %s.alignreport.er | samtools view -bS - | samtools sort -T %s - -o %s.trimmed.sorted.bam" % (bed, args.sample, args.sample, args.sample, args.sample, args.sample))
	cmds.append("align_trim.py --normalise 100 %s --report %s.alignreport.txt < %s.sorted.bam 2> %s.alignreport.er | samtools view -bS - | samtools sort -T %s - -o %s.primertrimmed.sorted.bam" % (bed, args.sample, args.sample, args.sample, args.sample, args.sample))
	cmds.append("samtools index %s.trimmed.sorted.bam" % (args.sample))
	cmds.append("samtools index %s.primertrimmed.sorted.bam" % (args.sample))

	#covplot.R $sample.alignreport.txt

	# 6) do variant calling using the raw signal alignment
	cmds.append("nanopolish variants --progress -t %s --reads %s.fasta -o %s.vcf -b %s.trimmed.sorted.bam -g %s -w \"%s\"  --snps --ploidy 1" % (args.threads, args.sample, args.sample, args.sample, ref, nanopolish_header))
	cmds.append("nanopolish variants --progress -t %s --reads %s.fasta -o %s.primertrimmed.vcf -b %s.primertrimmed.sorted.bam -g %s -w \"%s\" --snps --ploidy 1" % (args.threads, args.sample, args.sample, args.sample, ref, nanopolish_header))

	#python nanopore-scripts/expand-cigar.py --bam "$sample".primertrimmed.sorted.bam --fasta $ref | python nanopore-scripts/count-errors.py /dev/stdin > "$sample".errors.txt

	# 7) do phasing
	#nanopolish phase-reads --reads $sample.fasta --bam $sample.trimmed.sorted.bam --genome $ref $sample.vcf

	# 8) variant frequency plot
	cmds.append("vcfextract.py %s > %s.variants.tab" % (args.sample, args.sample))

	# 8) filter the variants and produce a consensus
	cmds.append("margin_cons.py %s %s.vcf %s.trimmed.sorted.bam a > %s.consensus.fasta" % (ref, args.sample, args.sample, args.sample))

	for cmd in cmds:
		print >>sys.stderr, colored.green("Running: ") + cmd
		retval = os.system(cmd)
		if retval != 0:
			print >>sys.stderr, colored.red('Command failed:' ) + cmd


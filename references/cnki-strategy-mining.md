# CNKI strategy mining

CNKI may be used as a domestic strategy source only within lawful access and license boundaries.

## Data levels

- **L0 metadata**: title, author, school, year, discipline, keywords.
- **L1 public abstract/table of contents/reference metadata**: use when publicly visible or lawfully accessed.
- **L2 local full text**: use only when the user lawfully provides local files.
- **L3 derived strategy**: non-verbatim aggregate patterns safe to keep in the open-source skill.

## Extract only strategies

Allowed extracted features:

- chapter sequence;
- heading depth;
- abstract move structure;
- introduction progression;
- literature review taxonomy;
- methodology components;
- results/discussion linkage;
- conclusion structure;
- citation density;
- risk patterns.

Do not store:

- full PDFs or Word files;
- long text passages;
- paragraphs that can reconstruct an original thesis;
- database credentials;
- scraping bypass methods.

## Sampling plan

For a large local corpus, stratify by:

- discipline;
- degree level;
- school type;
- year;
- methodology;
- thesis quality proxy when available.

## Output

Produce strategy cards and aggregate JSON. Each card must say it is a pattern, not a factual source.

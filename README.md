# sepsis-TDP-43-project

Project exploring serum TDP-43 and sepsis-associated encephalopathy.

## Automated literature crawler

This repository now contains a lightweight PubMed crawler that automates the
workflow previously carried out manually:

1. Gather background articles on serum TDP-43 in neurodegeneration and acute
   brain injury.
2. Focus on literature linking serum TDP-43 with sepsis-associated
   encephalopathy.
3. Collect comparator biomarkers such as NSE, S100β, and GFAP for benchmarking
   prognostic performance.

### Usage

```bash
python -m scraper.cli --output-dir data
```

The command will create JSON dumps for each query alongside a consolidated
`summary.md` file describing the retrieved papers. For every article, the
crawler also saves an EndNote (`.nbib`) citation named after the publication
title under `data/citations/<query_name>/`, providing one-to-one mapping between
the JSON records and reference files for easy importing into reference
managers.

### Testing

```bash
pytest
```

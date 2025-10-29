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

To enable the autonomous agent that can retry failed runs and apply
auto-corrections, append the `--agent-mode` flag. The agent will detect
download issues (for example citation failures or network pressure) and retry
with safer defaults such as skipping citation downloads or lowering the
`--max-articles` limit.

```bash
python -m scraper.cli --output-dir data --agent-mode --max-attempts 5
```

Key options:

- `--queries path/to/queries.json` – override the default queries with your own
  mapping of names to PubMed search strings.
- `--max-articles 100` – control how many results are downloaded per query,
  which is helpful for stress testing or keeping the dataset small while
  iterating.
- `--skip-citations` – disable EndNote downloads, which is useful when running
  repeated tests or when network bandwidth is constrained.
- `--agent-mode` – run the self-healing agent so that retries and automatic
  fixes (like toggling `--skip-citations`) are applied when the first attempt
  fails.

The command will create JSON dumps for each query alongside a consolidated
`summary.md` file describing the retrieved papers. For every article, the
crawler also saves an EndNote (`.nbib`) citation named after the publication
title under `data/citations/<query_name>/`, providing one-to-one mapping between
the JSON records and reference files for easy importing into reference
managers. When `--skip-citations` is used the JSON/Markdown outputs are still
generated and the run report will reflect that citation downloads were skipped.

### Testing

```bash
pytest
```

### Recommended development workflow

- **PyCharm (or another full IDE)** is best when iterating on the crawler code
  itself because it provides immediate feedback on typing issues, formatting,
  and packaging structure.
- **Jupyter notebooks** work well for exploratory analysis of the downloaded
  JSON and citation files when you want to quickly inspect or visualize the
  corpus.

Using both environments side-by-side mirrors typical literature-review
pipelines: maintain the production crawler in PyCharm while experimenting with
data post-processing in Jupyter.

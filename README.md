# ml-6g-mimo-ris-evidence-review

Data and code of the review *Scoring the Evidence Behind Machine Learning for 6G MIMO and RIS: A Systematic Review and Best-Evidence Synthesis of Seven Physical-Layer Areas*.

## Contents

| Path | Content |
|---|---|
| `data/search/` | OpenAlex export of the search with its manifest, and the counts of the screening log |
| `data/screening_log.csv` | One row per record, with the decisions on the title and abstract and on the full text |
| `data/assistant/ta_*` | Instructions and answers of the two screening runs |
| `data/assistant/ft_*` | Instructions and answers of the full-text readings, one JSON file per work |
| `data/assistant/ft_results.csv` | Charting form with the decisions, the grades, and the passages that support them |
| `data/assistant/author_corrections.csv` | Corrections of the author to the grades, with their passages |
| `data/best_supported_cells.csv` | Cells of the area tables |
| `data/citation_order.csv` | Order in which the section of each area cites the works of its table |
| `scripts/` | Code of the search, the screening log, the charting form, and every count, table, and figure |

`ft_first/` holds the first reading of every full text, `ft_second/` the second reading of each exclusion by the other model, `ft_published/` the grading of the published version of the preprints that met at least two criteria, and `ft_published_second/` the second reading of its exclusions. The first readings of the 28 works listed in `ft_first_v2.txt` followed `ft_instructions_v2.md`, and all other readings followed `ft_instructions.md`. The full texts are not released, since they belong to their publishers.

## Counts, tables, and figures

```
python3 scripts/evidence_stats.py
python3 scripts/best_supported_tables.py
python3 scripts/prisma_flow.py
python3 scripts/build_evidence_figures.py
```

The tables, the flow diagram, and the figures are written to `figures/`. The scripts use the Python standard library, except `build_evidence_figures.py`, which needs `pip install -r requirements.txt`, and `pdf_text.py`, the text extractor that the assistant used to read the full texts, which needs poppler.

## Rebuilding the screening log and the charting form

`scripts/search_openalex.py` ran the search on 21 October 2026, with the query and filter recorded in the manifest of the export. An OpenAlex API key is optional and is read from the `OPENALEX_API_KEY` environment variable. The SHA-256 in the manifest is that of the script as it ran, before its comments and two auxiliary commands were removed. To rebuild the log and the charting form from the export and the answers, delete `data/screening_log.csv`, `data/search/log_summary.json`, and `data/assistant/ft_results.csv` in a copy of the repository and run:

```
python3 scripts/build_log.py data/search/openalex_2026-10-21
python3 scripts/assistant_screening.py batches
python3 scripts/assistant_screening.py merge
python3 scripts/assistant_screening.py apply --agreed
python3 scripts/assistant_grading.py
```

The rebuilt files are identical to the released ones.

## License

MIT

from pathlib import Path

import typer

from .pipeline import run_pipeline

app = typer.Typer(help="Public email lead scraper for Texas blue-collar businesses.")


@app.command()
def scrape(
    seeds: Path = typer.Option(..., "--seeds", "-s", help="CSV file with at least a url column."),
    out: Path = typer.Option(Path("output/leads.csv"), "--out", "-o", help="CSV output path."),
    history: Path = typer.Option(Path("data/lead_history.csv"), "--history", help="Persistent CSV of previously exported leads."),
    dedupe: str = typer.Option("email", "--dedupe", help="Skip mode: none, email, domain, or email_or_domain."),
    max_pages: int = typer.Option(8, "--max-pages", help="Maximum pages to crawl per seed."),
    timeout: float = typer.Option(12.0, "--timeout", help="HTTP timeout in seconds."),
) -> None:
    """Crawl seed websites and export scored email leads."""
    total = run_pipeline(
        seeds_path=seeds,
        out_path=out,
        history_path=history,
        dedupe=dedupe,
        max_pages=max_pages,
        timeout=timeout,
    )
    typer.echo(f"Exported {total} lead rows to {out}")

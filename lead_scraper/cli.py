from pathlib import Path

import typer

from .exporter import export_direct_leads
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


@app.command("export-direct")
def export_direct(
    input_csv: Path = typer.Option(..., "--input", "-i", help="Raw scraper CSV to clean into a direct-lead list."),
    out: Path = typer.Option(Path("output/direct_leads.csv"), "--out", "-o", help="Direct-lead CSV output path."),
    keep_generic: bool = typer.Option(False, "--keep-generic", help="Keep generic inboxes like info@ and sales@."),
) -> None:
    """Export direct, non-generic emails in the downloadable lead CSV format."""
    saved, dropped = export_direct_leads(input_path=input_csv, output_path=out, drop_generic=not keep_generic)
    typer.echo(f"Exported {saved} direct lead rows to {out}")
    typer.echo(f"Dropped {dropped} duplicate or generic inbox rows")

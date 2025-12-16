#!/usr/bin/env python3
"""Scrape NvvP website for insurance reimbursements."""

import argparse
import json
from pathlib import Path
from copy import deepcopy
from collections import defaultdict
from typing import Any

from selenium import webdriver
from bs4 import BeautifulSoup


YearConfig = dict[str, str | None]

YEAR_CONFIGS: dict[str, YearConfig] = {
    "2023": {
        "url": "https://www.podotherapie.nl/vergoedingen/",
        "article_class": None,
    },
    "2024": {
        "url": "https://www.podotherapie.nl/vergoedingen/",
        "article_class": None,
    },
    "2025": {
        "url": "https://www.podotherapie.nl/vergoedingen/",
        "article_class": None,
    },
    "2026": {
        "url": "https://www.podotherapie.nl/vergoedingen2026",
        "article_class": "Article--collapsible",
    },
}


def html_to_json(part: Any) -> list[dict[str, str] | list[str]]:
    """Convert HTML table to JSON format.

    Parameters
    ----------
    part : BeautifulSoup element
        HTML table element to convert

    Returns
    -------
    list
        List of dictionaries or lists containing table data
    """
    rows = part.find_all("tr")

    headers: dict[int, str] = {}
    thead = part.find("thead")
    if thead:
        thead = thead.find_all("th")
        for i in range(len(thead)):
            headers[i] = thead[i].text.strip().lower()
    data: list[dict[str, str] | list[str]] = []
    for row in rows:
        cells = row.find_all("td")
        if thead:
            items_dict: dict[str, str] = {}
            if len(cells) > 0:
                for index in headers:
                    items_dict[headers[index]] = cells[index].text
            if items_dict:
                data.append(items_dict)
        else:
            items_list: list[str] = []
            for index in cells:
                items_list.append(index.text.strip())
            if items_list:
                data.append(items_list)

    return data


def scrape_year(year: str) -> dict[str, dict[str, Any]]:
    """Scrape insurance reimbursement data for a specific year.

    Parameters
    ----------
    year : str
        Year to scrape data for

    Returns
    -------
    dict
        Dictionary mapping provider names to their data
    """
    if year not in YEAR_CONFIGS:
        raise ValueError(
            f"Year {year} not configured. Available years: {list(YEAR_CONFIGS.keys())}"
        )

    config = YEAR_CONFIGS[year]

    options = webdriver.ChromeOptions()
    options.add_argument("headless")

    driver = webdriver.Chrome(options=options)
    url = config["url"]
    if url is None:
        raise ValueError(f"URL not configured for year {year}")
    driver.get(url)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    article_class = config["article_class"]
    if article_class:
        articles = soup.find_all("article", class_=article_class)
    else:
        articles = soup.find_all("article")[1].find_all("article")

    print(f"Found {len(articles)} articles on page for year {year}")

    providers: dict[str, dict[str, Any]] = {}
    for article in articles:
        button = article.find("button")
        if button is None:
            continue
        provider_name = button.text
        table = article.find("table")
        if table:
            products = html_to_json(table)
            providers[provider_name] = {
                "has_table": True,
                "products": products,
            }
        else:
            p_tag = article.find("p")
            if p_tag is None:
                continue
            info = p_tag.text
            providers[provider_name] = {
                "has_table": False,
                "info": info,
            }

    print(f"Restructured articles to {len(providers)} insurance providers")

    return providers


def save_to_json(
    providers: dict[str, dict[str, Any]], year: str, data_path: Path
) -> list[dict[str, str]]:
    """Save scraped data to JSON file.

    Parameters
    ----------
    providers : dict
        Provider data dictionary
    year : str
        Year of the data
    data_path : Path
        Directory path to save data

    Returns
    -------
    list
        List of formatted entries
    """
    table_press: list[dict[str, str]] = [
        {
            "verzekeraar": "Verzekeraar",
            "pakket": "Pakket",
            "vergoeding": "Vergoeding",
        }
    ]

    for provider, data in providers.items():
        if provider == "a.s.r.":
            products = deepcopy(data["products"])
            info = products.pop()
            additional_info = f"\n{info[0]}: {info[1]}"
            for product in products:
                table_press.append(
                    {
                        "verzekeraar": provider,
                        "pakket": product[0],
                        "vergoeding": product[1] + additional_info,
                    }
                )
        elif data["has_table"]:
            for product in data["products"]:
                table_press.append(
                    {
                        "verzekeraar": provider,
                        "pakket": product[0],
                        "vergoeding": product[1],
                    }
                )
        else:
            table_press.append(
                {
                    "verzekeraar": provider,
                    "pakket": "-",
                    "vergoeding": data["info"],
                }
            )

    if not data_path.exists():
        data_path.mkdir(parents=True)

    output_file = data_path / f"reimbursements_{year}.json"
    with open(output_file, "w") as f:
        json.dump(table_press, f, indent=4)

    print(f"Saved {len(table_press) - 1} entries to {output_file}")

    return table_press


def generate_comparison() -> (
    tuple[
        dict[str, list[dict[str, str]]],
        dict[str, dict[str, int]],
        list[str],
        list[str],
    ]
):
    """Generate comparison report across all available years.

    Returns
    -------
    tuple
        (all_years_data, provider_packages, all_providers, years)
    """
    data_path = Path(__file__).parent.parent / "data"

    all_years_data: dict[str, list[dict[str, str]]] = {}
    for year in YEAR_CONFIGS.keys():
        json_file = data_path / f"reimbursements_{year}.json"
        if json_file.exists():
            with open(json_file, "r") as f:
                data = json.load(f)
                all_years_data[year] = data[1:]

    provider_packages: dict[str, dict[str, int]] = defaultdict(dict)
    for year, entries in all_years_data.items():
        provider_counts: dict[str, int] = defaultdict(int)
        for entry in entries:
            provider = entry["verzekeraar"]
            provider_counts[provider] += 1

        for provider, count in provider_counts.items():
            provider_packages[provider][year] = count

    all_providers = sorted(provider_packages.keys())
    years = sorted(all_years_data.keys())

    return all_years_data, provider_packages, all_providers, years


def print_comparison() -> None:
    """Print comparison report to console."""
    all_years_data, provider_packages, all_providers, years = generate_comparison()

    print("\nTotal packages per year:")
    for year in years:
        total = len(all_years_data[year])
        print(f"  {year}: {total} packages")
    print()

    print(f"{'Provider':<40} {' '.join(f'{y:>6}' for y in years)}")
    print("=" * (40 + len(years) * 7))
    for provider in all_providers:
        year_counts = [
            str(provider_packages[provider].get(y, "-")).center(6) for y in years
        ]
        print(f"{provider:<40} {' '.join(year_counts)}")


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Scrape insurance reimbursement data from NvvP website"
    )
    parser.add_argument(
        "--year",
        type=str,
        choices=list(YEAR_CONFIGS.keys()),
        help="Year to scrape data for",
    )
    parser.add_argument(
        "--comparison",
        action="store_true",
        help="Generate comparison report across all available years",
    )

    args = parser.parse_args()

    if args.comparison:
        print_comparison()
    elif args.year:
        data_path = Path(__file__).parent.parent / "data"
        providers = scrape_year(args.year)
        save_to_json(providers, args.year, data_path)
    else:
        parser.print_help()
        print("\nError: Must specify either --year or --comparison")
        return 1

    return 0


if __name__ == "__main__":
    main()

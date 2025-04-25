# Ari - Personal Talent Agent

Find relevant jobs from company career pages before they hit mainstream platforms.

## Overview

Ari automatically discovers career pages from tech companies and monitors them for job listings that match your criteria. It's designed to give you an early advantage in your job search.

## Features

- Discovers career pages from company websites
- Extracts and filters job listings based on your criteria 
- Runs automatically via GitHub Actions
- Tracks ~3000 tech companies (expandable)

## Setup

```bash
git clone https://github.com/bharatbheesetti/ari.git
cd ari
pip install -r requirements.txt
playwright install
```

## Usage

### Find Career Pages

```bash
python career_page_url_finder.py companies_final.csv companies_with_careers.csv
```

### Extract Jobs

```bash
python job_scraper.py --csv companies_with_careers.csv [--format json|csv] [--headless]
```

## How It Works

1. **Career Page Discovery**: Uses multiple strategies to locate company career pages
2. **Job Extraction**: Scrapes and filters job listings matching your criteria
3. **Automated Monitoring**: GitHub Actions workflow runs daily

## Structure

```
ari/
├── career_page_url_finder.py   # Finds career pages
├── job_scraper.py              # Extracts job listings
├── companies_final.csv         # Input companies list
├── companies_with_careers.csv  # Companies with career URLs
└── .github/workflows/          # Automation workflows
```

## Current Status

The tool can successfully find career pages for companies and extract job listings. It's being refreshed with improved functionality for more accurate job matching.
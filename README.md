# Job Board Scraper

A simple tool to scrape job boards for relevant Product Manager positions in Bangalore/India/Remote.

## Setup and Usage

### One-Step Run

Just run the script:

```bash
python job_scraper.py
```

This will:
1. Set up the environment if needed
2. Install and start the local model server
3. Process all job boards in companies.csv
4. Export matching jobs to a JSON file

### Options

```bash
python job_scraper.py --setup    # Only run setup, don't scrape
python job_scraper.py --csv path_to_csv.csv  # Specify custom CSV file
python job_scraper.py --format csv  # Export as CSV instead of JSON
python job_scraper.py --headless  # Run browser in headless mode
```

## How It Works

The script:
1. Reads company names and job board URLs from companies.csv
2. Processes each job board using Proxy Lite's autonomous browsing capability
3. Searches for Product Manager roles with senior/lead levels in Bangalore/India/Remote
4. Extracts job details (title, company, description, location, etc.)
5. Filters results based on criteria
6. Exports to JSON or CSV

## Requirements

- Python 3.11
- Windows
- Approximately 8GB RAM for the local model

## Output Format

The output is saved as `job_results_[timestamp].json` with this structure:

```json
{
  "jobs": [
    {
      "title": "Senior Product Manager",
      "company": "Example Company",
      "description": "Job description text...",
      "location": "Bangalore, India",
      "url": "https://example.com/job",
      "posted_date": "Feb 2025",
      "source_url": "https://jobs.example.com",
      "extracted_at": "2025-02-28T12:34:56"
    },
    ...
  ],
  "metadata": {
    "generated_at": "2025-02-28T12:34:56",
    "total_jobs_found": 12
  }
}
```
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import importlib.util

# Check for pandas first
try:
    import pandas as pd
except ImportError:
    print("Installing pandas...")
    subprocess.run("pip install pandas", shell=True, check=True)
    import pandas as pd

# SIMPLIFIED FUNCTION TO HANDLE ALL SETUP
def ensure_environment():
    # Setup proxy-lite if needed
    proxy_lite_dir = Path("proxy-lite")
    if not proxy_lite_dir.exists():
        print("Setting up proxy-lite...")
        
        # Clone proxy-lite repository
        print("Cloning proxy-lite repository...")
        subprocess.run("git clone https://github.com/convergence-ai/proxy-lite.git", shell=True, check=True)
        
        # Install uv first (as specified in the README)
        print("Installing uv package manager...")
        subprocess.run("pip install uv", shell=True, check=True)
        
        # Setup according to README instructions
        os.chdir("proxy-lite")
        print("Creating venv with uv...")
        subprocess.run("uv venv --python 3.11 --python-preference managed", shell=True, check=True)
        print("Running uv sync...")
        subprocess.run("uv sync", shell=True, check=True)
        print("Installing proxy-lite...")
        subprocess.run("uv pip install -e .", shell=True, check=True)
        print("Installing playwright...")
        subprocess.run("playwright install", shell=True, check=True)
        os.chdir("..")
    
    # Try to import proxy_lite module
    proxy_spec = importlib.util.find_spec("proxy_lite")
    if not proxy_spec:
        # Add proxy-lite to Python path if not found
        print("Adding proxy-lite to Python path...")
        sys.path.insert(0, str(proxy_lite_dir / "src"))
    
    try:
        # Import proxy-lite
        from proxy_lite import Runner, RunnerConfig
    except ImportError:
        print("Error: Cannot import proxy_lite module.")
        print("Try installing manually according to the README:")
        print("cd proxy-lite")
        print("pip install uv")
        print("uv venv --python 3.11 --python-preference managed")
        print("uv sync")
        print("uv pip install -e .")
        print("playwright install")
        sys.exit(1)
    
    print("Using HuggingFace demo endpoint for the model (vLLM doesn't work well on Windows)")
    
    return Runner, RunnerConfig

# Load job boards from CSV
def load_job_boards(csv_file_path):
    df = pd.read_csv(csv_file_path)
    job_boards = []
    
    for _, row in df.iterrows():
        company_name = row.iloc[0]
        job_board_url = row.iloc[-1]
        
        if isinstance(job_board_url, str) and (
            job_board_url.startswith('http://') or 
            job_board_url.startswith('https://')
        ):
            job_boards.append({
                'company': company_name,
                'url': job_board_url
            })
    
    print(f"Loaded {len(job_boards)} job boards from CSV")
    return job_boards

# Main scraper function
async def scrape_job_board(Runner, RunnerConfig, job_board, headless=False):
    company = job_board['company']
    url = job_board['url']
    
    print(f"\nProcessing job board for {company}: {url}")
    
    # Set reasonable timeouts to prevent getting stuck
    per_site_timeout = 600  # 10 minutes per job board max
    max_steps = 50  # Reduce steps since we're being more focused now
    
    # Configure runner with HuggingFace demo endpoint
    config = RunnerConfig.from_dict({
        "environment": {
            "name": "webbrowser",
            "homepage": url,  # Direct URL without quotes/braces
            "headless": headless,
            "viewport_width": 1280,
            "viewport_height": 1080,
            "screenshot_delay": 2.0,
            "include_poi_text": True,
        },
        "solver": {
            "name": "simple",
            "agent": {
                "name": "proxy_lite",
                "client": {
                    "name": "convergence",
                    "model_id": "convergence-ai/proxy-lite-3b",
                    "api_base": "https://convergence-ai-demo-api.hf.space/v1",  # Using HuggingFace demo endpoint
                },
            },
        },
        "max_steps": max_steps,
        "action_timeout": 60,  # Shorter timeout per action
        "environment_timeout": 60,  # Shorter timeout for environment response
        "task_timeout": per_site_timeout,  # Overall timeout for the site
        "logger_level": "INFO",
    })
    
    try:
        # Initialize runner
        runner = Runner(config=config)
        
        # Create scraping instructions with clear success/fail conditions
        scraping_instructions = (
            f"You are now on the job board for {company} at {url}. "
            f"Look for Senior/Lead/Principal Product Manager jobs in Bangalore/Bengaluru or remote. "
            f"Focus ONLY on searching and browsing job listings - do not click on any other links. "
            f"If after exploring the site you find that: "
            f"1. There are no relevant job postings, or "
            f"2. You cannot access the job listings due to blocks/errors, or "
            f"3. You've searched through all available pages "
            f"Then say 'NO_RELEVANT_JOBS_FOUND' and explain briefly why. "
            f"Otherwise, collect the following for each relevant job listing: "
            f"1. Job title, 2. Company name ({company}), 3. Full job description, 4. Job location, 5. Job URL, 6. Posted date (if available) "
            f"Return the information in this JSON format: "
            f"[{{'title': 'Job Title', 'company': '{company}', 'description': 'Full description...', "
            f"'location': 'Job Location', 'url': 'Job URL', 'posted_date': 'Date if available'}}]"
        )
        
        # Use asyncio.wait_for to enforce timeout
        try:
            # Run the scraper with timeout
            result = await asyncio.wait_for(
                runner.run(scraping_instructions), 
                timeout=per_site_timeout
            )
            
            # Check if we need to move on due to no jobs
            if "NO_RELEVANT_JOBS_FOUND" in result.result:
                print(f"No relevant jobs found for {company} - moving to next site")
                return {
                    'company': company,
                    'source_url': url,
                    'result': '[]'  # Empty JSON array
                }
                
            # Return the result
            return {
                'company': company,
                'source_url': url,
                'result': result.result
            }
            
        except asyncio.TimeoutError:
            print(f"Timeout reached for {company} - moving to next site")
            return {
                'company': company,
                'source_url': url,
                'result': '[]'  # Empty JSON array
            }
            
    except Exception as e:
        print(f"Error processing job board {url}: {e}")
        return {
            'company': company,
            'source_url': url,
            'result': '[]'  # Empty JSON array
        }

# Parse job results
def parse_job_results(results):
    all_jobs = []
    
    for result in results:
        company = result['company']
        source_url = result['source_url']
        result_text = result['result']
        
        try:
            # Look for JSON-like structure in the text
            import re
            json_pattern = r'(\{[\s\S]*\}|\[[\s\S]*\])'
            json_matches = re.findall(json_pattern, result_text)
            
            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    
                    # Check if it's a list of jobs
                    if isinstance(data, list):
                        for job in data:
                            if isinstance(job, dict) and 'title' in job:
                                job['company'] = job.get('company', company)
                                job['source_url'] = source_url
                                job['extracted_at'] = datetime.now().isoformat()
                                all_jobs.append(job)
                    
                    # Check if it's a dict with jobs
                    elif isinstance(data, dict):
                        if 'jobs' in data and isinstance(data['jobs'], list):
                            for job in data['jobs']:
                                if isinstance(job, dict) and 'title' in job:
                                    job['company'] = job.get('company', company)
                                    job['source_url'] = source_url
                                    job['extracted_at'] = datetime.now().isoformat()
                                    all_jobs.append(job)
                        # Or a single job
                        elif 'title' in data:
                            data['company'] = data.get('company', company)
                            data['source_url'] = source_url
                            data['extracted_at'] = datetime.now().isoformat()
                            all_jobs.append(data)
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"Error parsing results from {company}: {e}")
    
    # Filter jobs to match criteria
    role_keywords = ["product manager", "product owner", "product lead"]
    seniority_keywords = ["senior", "group", "staff", "lead", "principal", "head"]
    location_keywords = ["bangalore", "bengaluru", "india", "remote"]
    
    filtered_jobs = []
    for job in all_jobs:
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        location = job.get('location', '').lower()
        
        # Check if role keywords match
        role_match = any(keyword in title.lower() for keyword in role_keywords)
        
        # Check if seniority keywords match
        seniority_match = any(keyword in title.lower() for keyword in seniority_keywords)
        
        # Check if location keywords match
        location_match = any(
            keyword in location.lower() or keyword in description.lower() 
            for keyword in location_keywords
        )
        
        if role_match and seniority_match and location_match:
            filtered_jobs.append(job)
    
    print(f"Found {len(filtered_jobs)} relevant jobs after filtering")
    return filtered_jobs

# Export results
def export_results(jobs, output_format="json"):
    if not jobs:
        print("No jobs found to export")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if output_format.lower() == 'json':
        output_file = f"job_results_{timestamp}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'jobs': jobs,
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'total_jobs_found': len(jobs)
                }
            }, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(jobs)} jobs to {output_file}")
    
    elif output_format.lower() == 'csv':
        output_file = f"job_results_{timestamp}.csv"
        pd.DataFrame(jobs).to_csv(output_file, index=False, encoding='utf-8')
        print(f"Exported {len(jobs)} jobs to {output_file}")
    
    else:
        print(f"Unsupported output format: {output_format}")

# Main function
async def main():
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Job Board Scraper')
    parser.add_argument('--csv', type=str, default='companies.csv', help='Path to companies CSV file')
    parser.add_argument('--format', type=str, choices=['json', 'csv'], default='json', help='Output format')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    args = parser.parse_args()
    
    # Setup everything in one step
    Runner, RunnerConfig = ensure_environment()
    
    # Load job boards from CSV
    job_boards = load_job_boards(args.csv)
    if not job_boards:
        print("No valid job boards found in CSV. Exiting.")
        return
    
    # Process each job board
    results = []
    for i, job_board in enumerate(job_boards):
        print(f"Processing job board {i+1}/{len(job_boards)}")
        result = await scrape_job_board(Runner, RunnerConfig, job_board, args.headless)
        results.append(result)
        # Show progress update
        print(f"Completed {i+1}/{len(job_boards)} job boards")
        # Add a short delay between job boards
        await asyncio.sleep(5)
    
    # Parse and export results
    jobs = parse_job_results(results)
    export_results(jobs, args.format)

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import argparse
import os
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv

from google.adk.agents import Agent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# ---------------------------------------------------------
# 1. Location Resolution
# ---------------------------------------------------------
COUNTRY_MAP = {
    "germany": "DE",
    "uk": "UK",
    "united kingdom": "UK",
    "netherlands": "NL",
    "france": "FR",
    "spain": "ES",
    "portugal": "PT",
    "ireland": "IE",
    "belgium": "BE",
    "sweden": "SE",
    "denmark": "DK",
    "switzerland": "CH",
    "austria": "AT",
    "italy": "IT",
    "poland": "PL",
    "malaysia": "MY",
    "singapore": "SG",
    "australia": "AU",
    "usa": "USA",
    "united states": "USA",
    "canada": "CA",
}

def resolve_location(user_input: str) -> tuple[str, str]:
    """
    Returns (location_string, country_code) from user input.
    Example: "Berlin" or "Germany" → ("Berlin", "DE")
    """
    text = user_input.strip().lower()
    country_code = "UK"  # default fallback

    for key, code in COUNTRY_MAP.items():
        if key in text:
            country_code = code
            break

    location = user_input.strip().title()
    return location, country_code


# ---------------------------------------------------------
# 2. Real Job Search Tool (calls RapidAPI)
# ---------------------------------------------------------
def search_jobs(query: str, location: str = "London", country_code: str = "UK") -> str:
    """
    Searches live job boards for open roles matching the query.
    Returns a formatted string summary of the top 3 results.
    """
    stop_words = {"please", "find", "me", "a", "in", "and", "the", "my", "for", "i", "am"}
    words = [w for w in query.split() if w.lower() not in stop_words]
    clean_query = " ".join(words[:4])

    print(f"\n[ SYSTEM: search_jobs | query='{clean_query}' | location='{location}' | country='{country_code}' ]\n")

    url = "https://jobs-search-api.p.rapidapi.com/getjobs_excel"

    payload = {
        "search_term": clean_query,
        "location": location,
        "country_indeed": country_code,
        "results_wanted": 3,
        "site_name": ["indeed", "linkedin", "glassdoor"],
        "distance": 100,
        "job_type": "fulltime",
        "is_remote": True,
        "linkedin_fetch_description": True,
        "hours_old": 72
    }

    headers = {
        "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
        "x-rapidapi-host": "jobs-search-api.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()

        df = pd.read_excel(BytesIO(response.content))

        if df.empty:
            return "No jobs found matching the query."

        jobs_summary = []
        for i, job in df.head(3).iterrows():
            jobs_summary.append(
                f"--- Job {i+1} ---\n"
                f"Company: {job.get('company', 'N/A')}\n"
                f"Role: {job.get('title', 'N/A')}\n"
                f"Location: {job.get('location', 'N/A')}\n"
                f"Description: {str(job.get('description', 'N/A'))[:400]}\n"
                f"URL: {job.get('job_url', 'N/A')}\n"
            )

        print(f"[ SYSTEM: Found {len(jobs_summary)} job(s) ]\n")
        return "\n".join(jobs_summary)

    except Exception as e:
        print(f"[ SYSTEM: API error -> {e} ]")
        return (
            f"API error: {str(e)}. Using fallback data: "
            f"Company: Adyen, Role: Product Manager, Location: Amsterdam, "
            f"Description: API compliance migration role requiring B2B Fintech experience."
        )


# ---------------------------------------------------------
# 3. File Output
# ---------------------------------------------------------
def save_output(cv: str, role: str, location: str, country_code: str,
                email_text: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"job_outreach_{timestamp}.txt")

    content = f"""JOB HUNTER PIPELINE — OUTPUT
Generated : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
{'=' * 60}

INPUT
-----
CV       : {cv}
Role     : {role}
Location : {location} ({country_code})

{'=' * 60}

OUTREACH EMAIL DRAFT
--------------------
{email_text}

{'=' * 60}
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    return filename


# ---------------------------------------------------------
# 4. CLI Args
# ---------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="🚀 Job Hunter Pipeline — Powered by Gemini + ADK",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--cv", required=True,
        help="Your CV summary\nExample: '7 years Fintech Delivery Lead, MSc KU Leuven'"
    )
    parser.add_argument(
        "--role", required=True,
        help="Role you are targeting\nExample: 'Senior Product Manager'"
    )
    parser.add_argument(
        "--location", required=True,
        help="Target city or country\nExample: 'Berlin' or 'Germany'"
    )
    parser.add_argument(
        "--output", default="outputs",
        help="Folder to save results (default: ./outputs)"
    )
    return parser.parse_args()


# ---------------------------------------------------------
# 5. Static Agents (strategist + copywriter don't need location)
# ---------------------------------------------------------
strategist_agent = Agent(
    name="strategist_agent",
    model="gemini-2.5-flash",
    instruction="""
    You are an elite Tech Career Strategist.

    From {{found_job_data}}, pick the ONE job that best matches the candidate's CV.
    Then identify the strongest overlap between their skills and that job's core problem.
    Output:
    - Chosen job (company + role + URL)
    - A 2-sentence Hook explaining the match

    Save to session state via output_key.
    """,
    output_key="candidate_hook"
)

copywriter_agent = Agent(
    name="copywriter_agent",
    model="gemini-2.5-flash",
    instruction="""
    You are an expert B2B copywriter.
    Using {{candidate_hook}} and {{found_job_data}}, draft a cold outreach email.

    Rules:
    - Subject line: specific to the role and company, no generic titles
    - Greeting: use Hiring Manager name if known, otherwise "Hi [Company] Team,"
    - Never leave placeholders like [Your Name] or [Title] — omit unknown info entirely
    - Max 4 sentences in the body. End with a single clear CTA (e.g. "Open to a 20-min call?")
    - Tone: direct, confident, not sycophantic
    """
)


# ---------------------------------------------------------
# 6. Main
# ---------------------------------------------------------
async def main():
    args = parse_args()
    location, country_code = resolve_location(args.location)

    print(f"\n🚀 Job Hunter Pipeline — Gemini + ADK")
    print(f"{'=' * 60}")
    print(f"📄 CV       : {args.cv}")
    print(f"🎯 Role     : {args.role}")
    print(f"📍 Location : {location} ({country_code})")
    print(f"{'=' * 60}\n")

    # Build location-aware tool as a closure
    def search_jobs_with_location(query: str) -> str:
        """Searches live job boards for open roles matching the query."""
        return search_jobs(query, location=location, country_code=country_code)

    # Scout agent built per-run (needs the closure tool)
    scout_agent = Agent(
        name="scout_agent",
        model="gemini-2.5-flash",
        tools=[search_jobs_with_location],
        instruction="""
        You are a Tech Career Scout.

        Step 1: Extract a SHORT search query (max 4 words): job title + industry only.
                Example: "Product Manager Fintech"

        Step 2: Call `search_jobs_with_location` ONCE with that query. Do not retry.

        Step 3: Extract Company Name, Role, Location, and Job Description from the results.
                Save to session state via output_key.
        """,
        output_key="found_job_data"
    )

    pipeline = SequentialAgent(
        name="job_hunter_pipeline",
        sub_agents=[scout_agent, strategist_agent, copywriter_agent]
    )

    user_prompt = f"""
    My CV: {args.cv}
    My Request: Find me a {args.role} role and draft my outreach email.
    Target Location: {location} ({country_code})
    """

    print("🔍 Scanning live job boards...")
    print("✍️  Agents working...\n")

    session_service = InMemorySessionService()
    runner = Runner(
        agent=pipeline,
        app_name="hackathon_app",
        session_service=session_service
    )
    session = await session_service.create_session(
        app_name="hackathon_app",
        user_id="user_session"
    )

    final_email = ""
    async for event in runner.run_async(
        user_id="user_session",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=user_prompt)])
    ):
        if event.is_final_response():
            final_email = event.content.parts[0].text

    # Print to terminal
    print("\n✅ FINAL OUTREACH DRAFT:\n")
    print(final_email)
    print(f"\n{'=' * 60}")

    # Save to file
    saved_path = save_output(
        args.cv, args.role, location, country_code, final_email, args.output
    )
    print(f"💾 Saved to: {saved_path}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
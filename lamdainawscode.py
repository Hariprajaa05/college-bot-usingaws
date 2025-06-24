import json
import boto3
import time
import re
from collections import Counter
from string import punctuation

# AWS Clients
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# Stopwords for filtering
STOPWORDS = set("""
a an the and or in on of for with to from by at is was as are be this that which it its has have not their
""".split())

# ---------- UTILITIES ----------

def read_file_from_s3(bucket, key):
    print(f"Reading file: {key}")
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj['Body'].read().decode('utf-8')

def tokenize(text):
    text = re.sub(rf"[{punctuation}]", "", text.lower())
    tokens = text.split()
    return [word for word in tokens if word not in STOPWORDS]

def chunk_text(text, chunk_size=1000, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def score_chunk(chunk, question_tokens):
    chunk_tokens = tokenize(chunk)
    counter = Counter(chunk_tokens)
    return sum(counter[token] for token in question_tokens)

def find_best_chunks(text, question, top_n=3):
    question_tokens = tokenize(question)
    chunks = chunk_text(text)
    scored_chunks = [(chunk, score_chunk(chunk, question_tokens)) for chunk in chunks]
    sorted_chunks = sorted(scored_chunks, key=lambda x: x[1], reverse=True)
    best_chunks = [chunk for chunk, score in sorted_chunks[:top_n]]
    combined = "\n\n".join(best_chunks)
    return combined[:6000]

def ask_claude(context, question):
    prompt = f"""Use the following college info to answer this question:\n\n{context}\n\nQuestion: {question}"""
    time.sleep(1)
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500
        }),
        contentType="application/json",
        accept="application/json"
    )
    return json.loads(response['body'].read())['content'][0]['text']

# ---------- MAIN HANDLER ----------

def lambda_handler(event, context):
    # Safe access to query
    question = event.get("queryStringParameters", {}).get("q", "").strip()

    if not question:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing query parameter 'q'"})
        }

    bucket = "college-ai-data"
    keys = [
        "conferencepapers.json",
        "courses.json",
        "elective_courses.json",
        "faculty.json",
        "faqs.json",
        "industry_projects.json"
    ]

    try:
        lower_q = question.lower()

        # Faculty-related questions
        faculty_keywords = ["faculty", "professor", "staff", "teacher", "vignesh", "sarvanan", "hod"]
        if any(word in lower_q for word in faculty_keywords):
            print("→ Faculty-related question detected.")
            faculty_text = read_file_from_s3(bucket, "faculty.json")

            # List all faculty
            if "list" in lower_q and "faculty" in lower_q:
                try:
                    faculty_data = json.loads(faculty_text)
                    if isinstance(faculty_data, list):
                        faculty_list = faculty_data
                    elif isinstance(faculty_data, dict):
                        faculty_list = faculty_data.get("faculty", [])
                    else:
                        faculty_list = []

                    output = []
                    for i, faculty in enumerate(faculty_list, 1):
                        name = faculty.get("Name", "Unknown")
                        designation = faculty.get("Title", "Faculty")
                        output.append(f"{i}. {name} ({designation})")

                    return {
                        "statusCode": 200,
                        "headers": {"Access-Control-Allow-Origin": "*"},
                        "body": json.dumps({"answer": "Faculty Members:\n\n" + "\n".join(output)})
                    }

                except Exception as e:
                    return {
                        "statusCode": 500,
                        "body": json.dumps({"error": f"Could not parse faculty.json: {str(e)}"})
                    }

            # Specific faculty like "Vignesh"
            if "vignesh" in lower_q:
                return {
                    "statusCode": 200,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"answer": faculty_text[:3000]})
                }

            # General faculty Claude response
            combined_text = faculty_text
            for key in keys:
                if key != "faculty.json":
                    combined_text += read_file_from_s3(bucket, key) + "\n\n"
            best_context = find_best_chunks(combined_text, question)
            answer = ask_claude(best_context, question)
            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": answer})
            }

        # Course code (e.g., EP101)
        if re.match(r"[A-Z]{2,4}\d{3}", question.strip().upper()):
            print("→ Course code pattern detected.")
            combined_text = (
                read_file_from_s3(bucket, "courses.json") + "\n\n" +
                read_file_from_s3(bucket, "elective_courses.json") + "\n\n"
            )
            for key in keys:
                if key not in ["courses.json", "elective_courses.json"]:
                    combined_text += read_file_from_s3(bucket, key) + "\n\n"
            best_context = find_best_chunks(combined_text, question)
            answer = ask_claude(best_context, question)
            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": answer})
            }

        # Conference papers
        if "conference" in lower_q or "paper" in lower_q or "authors" in lower_q:
            print("→ Conference paper question detected.")
            combined_text = read_file_from_s3(bucket, "conferencepapers.json") + "\n\n"
            for key in keys:
                if key != "conferencepapers.json":
                    combined_text += read_file_from_s3(bucket, key) + "\n\n"
            best_context = find_best_chunks(combined_text, question)
            answer = ask_claude(best_context, question)
            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": answer})
            }

        # Industry Projects
        industry_keywords = [
            "industry project", "industry projects", "company", "companies",
            "internship", "internships", "collaboration", "collaborations",
            "geons", "students involved", "project name", "project", "projects"
        ]
        if any(word in lower_q for word in industry_keywords):
            print("→ Industry project question detected.")
            combined_text = read_file_from_s3(bucket, "industry_projects.json") + "\n\n"
            for key in keys:
                if key != "industry_projects.json":
                    combined_text += read_file_from_s3(bucket, key) + "\n\n"
            best_context = find_best_chunks(combined_text, question)
            answer = ask_claude(best_context, question)
            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": answer})
            }

        # FAQs and Vision/Mission
        faq_keywords = ["vision", "mission", "outcome", "objectives", "goal", "department aim"]
        if any(word in lower_q for word in faq_keywords):
            print("→ FAQ/vision/mission question detected.")
            combined_text = read_file_from_s3(bucket, "faqs.json") + "\n\n"
            for key in keys:
                if key != "faqs.json":
                    combined_text += read_file_from_s3(bucket, key) + "\n\n"
            best_context = find_best_chunks(combined_text, question)
            answer = ask_claude(best_context, question)
            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": answer})
            }

        # Default fallback
        print("→ Default: combining all files.")
        combined_text = ""
        for key in keys:
            combined_text += read_file_from_s3(bucket, key) + "\n\n"

        best_context = find_best_chunks(combined_text, question)
        answer = ask_claude(best_context, question)

        return {
            "statusCode": 200,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"answer": answer})
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

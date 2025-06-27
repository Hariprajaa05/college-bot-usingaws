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
    department = event.get("queryStringParameters", {}).get("department", "cse")
    dept_prefix = department.lower() + "/"

    if not question:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing query parameter 'q'"})
        }

    bucket = "college-ai-data"
    filenames = [
        "conferencepapers.json",
        "courses.json",
        "elective_courses.json",
        "faculty.json",
        "faqs.json",
        "industry_projects.json",
        "coursesyllabus.json",
        "industrial_project_ideas.json",
        "important_questions_links.json"
    ]
    keys = [dept_prefix + name for name in filenames]



    try:
        lower_q = question.lower()

        # Faculty-related questions
        faculty_keywords = ["faculty", "professor", "staff", "teacher", "hod"]
        if any(word in lower_q for word in faculty_keywords):
            print("→ Faculty-related question detected.")
            dept_prefix = department.lower() + "/"  # example: "cse/"
            faculty_text = read_file_from_s3(bucket, dept_prefix + "faculty.json")


            faculty_data = json.loads(faculty_text)
            if isinstance(faculty_data, dict):
                faculty_data = faculty_data.get("faculty", [])

            # If "list faculty" is asked
            if "list" in lower_q and "faculty" in lower_q:
                output = []
                for i, faculty in enumerate(faculty_data, 1):
                    name = faculty.get("Name", "Unknown")
                    title = faculty.get("Title", "Faculty")
                    output.append(f"{i}. {name} ({title})")

                return {
                    "statusCode": 200,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"answer": "Faculty Members:\n\n" + "\n".join(output)})
                }

            # Search for specific faculty by name
            matched = []
            for fac in faculty_data:
                name = fac.get("Name", "").lower()
                if any(part in lower_q for part in name.split()):
                    matched.append(fac)

            if matched:
                formatted_list = []
                for fac in matched:
                    formatted = f"""Name: {fac.get("Name")}
Title: {fac.get("Title")}
Email: {fac.get("Email")}
Phone: {fac.get("Phone")}
Qualification: {fac.get("Qualification")}
Research Interests: {fac.get("Research_Of_Interest")}
Achievements:\n- {chr(10).join(json.loads(fac.get("Achievements", "[]")))}"""
                    formatted_list.append(formatted)

                return {
                    "statusCode": 200,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"answer": "\n\n".join(formatted_list)})
                }

            # If no match, fallback to Claude
            combined_text = faculty_text
            for key in keys:
                if not key.endswith("faculty.json"):
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
            combined_text = read_file_from_s3(bucket, dept_prefix + "conferencepapers.json")+ "\n\n"
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
        # Project Topic Suggestions by Domain
        project_keywords = [
            "project topics", "project ideas", "mini project", "final year project", "domain projects",
            "ai project", "iot project", "cloud project", "data science project", "cybersecurity project",
            "blockchain project", "web development project", "mobile app project"
        ]

        if any(word in lower_q for word in project_keywords):
            print("→ Project domain suggestion detected.")
            project_data = json.loads(read_file_from_s3(bucket, dept_prefix + "industrial_project_ideas.json"))

            matched_domains = []
            response_lines = []

            for domain in project_data:
                if domain.lower() in lower_q:
                    matched_domains.append(domain)

            if matched_domains:
                for domain in matched_domains:
                    response_lines.append(f"🔷 **{domain} Projects:**")
                    for topic in project_data[domain]:
                        response_lines.append(f"• {topic}")
                    response_lines.append("")  # Empty line for spacing
            else:
                # No specific domain matched – list all
                for domain, topics in project_data.items():
                    response_lines.append(f"🔷 **{domain} Projects:**")
                    for topic in topics:
                        response_lines.append(f"• {topic}")
                    response_lines.append("")

            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": "\n".join(response_lines)})
            }
        # ✅ Industry Projects
        industry_keywords = [
            "industry project", "industry projects", "company", "companies",
            "internship", "internships", "collaboration", "collaborations",
            "geons", "students involved",
            "duration", "status"
        ]

        if any(word in lower_q for word in industry_keywords) or "project" in lower_q or "tell me about" in lower_q or "list" in lower_q:
            print("→ Industry project question detected.")

            # Read the industry projects JSON
            try:
                industry_json = read_file_from_s3(bucket, dept_prefix + "industry_projects.json")
                projects = json.loads(industry_json)
            except Exception as e:
                return {
                    "statusCode": 500,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"answer": f"❌ Failed to load project data: {str(e)}"})
                }

            matched_projects = []

            # Match specific project name or general listing
            for project in projects:
                project_name = project.get("project_name", "").lower()
                industry_name = project.get("industry_name", "").lower()
                students = project.get("students_involved", "").lower()

                if (
                    project_name in lower_q
                    or industry_name in lower_q
                    or any(student.strip() in lower_q for student in students.split(","))
                ):
                    matched_projects.append(project)

            # General listing of all if "list", "all", or "display" in query
            if not matched_projects and any(word in lower_q for word in ["list", "all", "display", "show"]):
                matched_projects = projects

            # If we found matches, format nicely
            if matched_projects:
                lines = []
                for proj in matched_projects:
                    lines.append(
                        f"🏭 *{proj.get('project_name', 'N/A')}* at _{proj.get('industry_name', 'N/A')}_\n"
                        f"👨‍🎓 Students: {proj.get('students_involved', 'N/A')}\n"
                        f"📅 Duration: {proj.get('duration', 'N/A')}\n"
                        f"✅ Status: {proj.get('status', 'N/A')}\n"
                    )
                answer = "\n\n".join(lines)
            else:
                answer = "⚠️ Sorry, no matching industry project information found for your query."

            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": answer})
            }


        # FAQs and Vision/Mission
        faq_keywords = ["vision", "mission", "outcome", "objectives", "goal", "department aim"]
        if any(word in lower_q for word in faq_keywords):
            print("→ FAQ/vision/mission question detected.")
            combined_text = read_file_from_s3(bucket, dept_prefix + "faqs.json") + "\n\n"
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
        
        # 📘 Important Question Links (by semester or subject)
        important_keywords = [
            "important question", "important questions link", "important links", "youtube links",
            "video links", "question links", "sem videos", "semester videos", "unit links"
        ]

        if any(word in lower_q for word in important_keywords):
            print("→ Important question link request detected.")
            link_data = json.loads(read_file_from_s3(bucket, dept_prefix + "important_questions_links.json"))

            sem_map = {
                "1": "Semester 1", "first": "Semester 1", "sem 1": "Semester 1",
                "2": "Semester 2", "second": "Semester 2", "sem 2": "Semester 2",
                "3": "Semester 3", "third": "Semester 3", "sem 3": "Semester 3",
                "4": "Semester 4", "fourth": "Semester 4", "sem 4": "Semester 4",
                "5": "Semester 5", "fifth": "Semester 5", "sem 5": "Semester 5",
                "6": "Semester 6", "sixth": "Semester 6", "sem 6": "Semester 6",
                "7": "Semester 7", "seventh": "Semester 7", "sem 7": "Semester 7",
                "8": "Semester 8", "eighth": "Semester 8", "sem 8": "Semester 8",
            }

            # 🔍 1. Check for semester-level request (with better matching)
            found_semester = None
            for key, label in sem_map.items():
                # Use whole-word regex match to avoid partial or fuzzy issues
                if re.search(rf"\b{re.escape(key)}\b", lower_q):
                    found_semester = label
                    break

            print(f"Resolved semester from query: {found_semester}")

            if found_semester and found_semester in link_data:
                links = link_data[found_semester]
                response_lines = [f"🎓 **{found_semester} Important Question Links:**\n"]
                for subject, url in links.items():
                    response_lines.append(f"🔗 [{subject}]({url})")
                return {
                    "statusCode": 200,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"answer": "\n".join(response_lines)})
                }


            # 🔍 2. Check for subject-level request
            for sem, subjects in link_data.items():
                for subject, url in subjects.items():
                    if subject.lower() in lower_q:
                        return {
                            "statusCode": 200,
                            "headers": {"Access-Control-Allow-Origin": "*"},
                            "body": json.dumps({
                                "answer": f"🔗 **{subject}** ({sem})\n[Click here for Important Question Link]({url})"
                            })
                        }

            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({
                    "answer": "Sorry, I couldn't find the important question links for that subject or semester. Please check the spelling or try asking again!"
                })
            }
        # Syllabus / Semester-wise Course Info
        syllabus_keywords = [
            "semester", "syllabus", "unit", "lesson", "topics", "subjects","units", 
            "second sem", "third sem", "first sem", "fourth sem", "fifth sem", 
            "sixth sem", "seventh sem", "eighth sem", "sem i", "sem ii", "sem iii",
            "sem iv", "sem v", "sem vi", "sem vii", "sem viii"
        ]

        if any(word in lower_q for word in syllabus_keywords):
            print("→ Syllabus or semester-wise question detected.")
            syllabus_text = read_file_from_s3(bucket, dept_prefix + "coursesyllabus.json")
            syllabus_data = json.loads(syllabus_text)

            response_texts = []

            # ✅ Iterate through all departments in the syllabus JSON
            for dept_key, dept_syllabus in syllabus_data.items():
                for semester, subjects in dept_syllabus.items():
                    # Normalize semester name for matching
                    normalized_sem = semester.lower().replace("_", " ")
                    if normalized_sem in lower_q or semester[-1] in lower_q:
                        response_texts.append(f"📘 **{dept_key.replace('_', ' ')} - {semester.replace('_', ' ')} Courses**:\n")
                        for code, info in subjects.items():
                            title = info.get("title", "Untitled")
                            units = info.get("units", [])
                            response_texts.append(f"🔹 {code} - {title}\nUnits:\n" + "\n".join([f"  - {unit}" for unit in units]) + "\n")

            if response_texts:
                return {
                    "statusCode": 200,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"answer": "\n".join(response_texts)})
                }

            # 🔁 Fallback to Claude or LLM
            combined_text = syllabus_text
            for key in keys:
                if key != "coursesyllabus.json":
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
                read_file_from_s3(bucket, dept_prefix + "courses.json") + "\n\n" +
                read_file_from_s3(bucket, dept_prefix + "elective_courses.json") + "\n\n"
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

        if "elective courses" in lower_q or "open elective" in lower_q or "professional elective" in lower_q:
            print("→ Elective courses query detected.")
            elective_text = read_file_from_s3(bucket, dept_prefix + "elective_courses.json")
            elective_data = json.loads(elective_text)

            response_lines = ["📘 **Elective Courses Offered:**\n"]

            for course in elective_data:
                code = course.get("course_code", "N/A")
                name = course.get("course_name", "N/A")
                category = course.get("category", "N/A")
                credits = course.get("credits", "N/A")
                periods = course.get("periods_per_week", "N/A")

                response_lines.append(f"🔹 {code} - {name} ({category}) – {credits} Credits – {periods}")

            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"answer": "\n".join(response_lines)})
            }




        # ✅ Default fallback if nothing matched
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


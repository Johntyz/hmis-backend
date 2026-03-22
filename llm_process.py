import sys
import os
from groq import Groq
import os
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
print("Script started...")

try:
    client = Groq(api_key = os.getenv("GROQ_API_KEY"))
    print("Groq configured successfully...")
except Exception as e:
    print(f"Failed to configure Groq: {e}")
    sys.exit(1)

def read_input_file(input_path: str):
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    if "FILES:" not in content:
        print("Error: input.txt must have a FILES: section.")
        sys.exit(1)

    # Extract app name
    if "APP:" not in content:
        print("Error: input.txt must have an APP: section at the top.")
        sys.exit(1)

    app_name = content.split("APP:")[1].split("\n")[0].strip()
    print(f"App: {app_name}")

    files_section = content.split("FILES:")[1].strip()
    file_paths = [line.strip() for line in files_section.splitlines() if line.strip()]

    # Extract all prompts
    prompts = []
    sections = content.split("FILES:")[0]

    if "PROMPT_1:" in sections and "PROMPT_2:" in sections:
        prompt1 = sections.split("PROMPT_1:")[1].split("PROMPT_2:")[0].strip()
        prompt2 = sections.split("PROMPT_2:")[1].strip()
        prompts.append((f"{app_name}_SYSTEM_MEMORY.md", prompt1))
        prompts.append((f"{app_name}_FRONTEND_CONTRACT.md", prompt2))
    elif "PROMPT:" in sections:
        prompt = sections.split("PROMPT:")[1].strip()
        prompts.append((f"{app_name}_llm_output.md", prompt))
    else:
        print("Error: input.txt must have either PROMPT: or PROMPT_1: and PROMPT_2: sections.")
        sys.exit(1)

    return prompts, file_paths

def read_files(file_paths: list) -> str:
    combined_content = ""
    for path in file_paths:
        print(f"Reading file: {path}")
        if not os.path.exists(path):
            print(f"Warning: {path} not found, skipping.")
            continue
        with open(path, "r", encoding="utf-8") as f:
            combined_content += f"\n\n--- File: {path} ---\n{f.read()}"
    return combined_content

def process_prompt(prompt: str, file_contents: str) -> str:
    full_prompt = f"{prompt}\n\n{file_contents}"
    print("Sending to Groq...")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": full_prompt}]
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(script_dir, "input.txt")

    if not os.path.exists(input_file):
        print(f"Error: input.txt not found in {script_dir}")
        sys.exit(1)

    print(f"Reading input from: {input_file}")
    prompts, files = read_input_file(input_file)

    print(f"Files to process: {len(files)}")
    file_contents = read_files(files)

    if not file_contents:
        print("No valid files were read.")
        sys.exit(1)

    for output_filename, prompt in prompts:
        print(f"\nGenerating {output_filename}...")
        try:
            result = process_prompt(prompt, file_contents)
            output_path = os.path.join(script_dir, output_filename)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"--- Saved to {output_path} ---")
        except Exception as e:
            print(f"Error generating {output_filename}: {e}")
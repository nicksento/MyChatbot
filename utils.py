"""
utils.py

This module provides utility functions that are commonly used throughout the project. 
It is designed to include reusable, generic helper methods that can be imported and 
used in different parts of the application.
"""

import os
import re
import time
import arxiv
import requests
import chainlit as cl
import google.generativeai as genai

async def get_arxiv_documents(query, max_results):
    """Retrieves documents from arXiv based on a query."""
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )

    documents = []
    for result in search.results():
        documents.append({
            "title": result.title,
            "summary": result.summary,
            "pdf_url": result.pdf_url,
            "authors": [author.name for author in result.authors],
            "published": result.published.strftime("%Y-%m-%d")
        })
    return documents


def sanitize_filename(filename):
    """Remove invalid characters for filenames"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def download_pdf(url, directory, filename):
    """Download pdf from URL"""
    try:
        # Create the directory if it doesn't exist
        if not os.path.exists(directory):
            os.makedirs(directory)

        # Remove invalid characters
        filename = sanitize_filename(filename)

        # Construct the full path for the file
        output_path = os.path.join(directory, filename)

        # Send a GET request to the URL
        response = requests.get(url, stream=True, timeout=60)

        # Check if the request was successful
        if response.status_code == 200:
            # Write the content of the response as binary to the specified file
            with open(output_path, 'wb') as file:
                file.write(response.content)
            print(f"PDF downloaded successfully and saved to {output_path}")
            return output_path
        else:
            print(f"Failed to download PDF. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {e}")


def upload_to_gemini(path, mime_type=None):
    """Uploads the given file to Gemini.

    See https://ai.google.dev/gemini-api/docs/prompting_with_media
    """
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file

def wait_for_files_active(files):
    """Waits for the given files to be active.

    Some files uploaded to the Gemini API need to be processed before they can be
    used as prompt inputs. The status can be seen by querying the file's "state"
    field.

    This implementation uses a simple blocking polling loop. Production code
    should probably employ a more sophisticated approach.
    """
    print("Waiting for file processing...")
    for name in (file.name for file in files):
        file = genai.get_file(name)
    while file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(10)
        file = genai.get_file(name)
    if file.state.name != "ACTIVE":
        raise Exception(f"File {file.name} failed to process")
    print("...all files ready")
    print()

def delete_directory(directory_path):
    try:
        # Iterate over all items in the directory
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            # Check if it's a file or directory
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)  # Delete the file or link
            elif os.path.isdir(item_path):
                delete_directory(item_path)  # Recursively delete subdirectory
        os.rmdir(directory_path)  # Finally, delete the empty directory
        print(f"Directory '{directory_path}' has been deleted.")
    except FileNotFoundError:
        print(f"Directory '{directory_path}' not found.")
    except PermissionError:
        print(f"Permission denied to delete '{directory_path}'.")
    except Exception as e:
        print(f"Error: {e}")

async def get_documents(topic):
    documents = await get_arxiv_documents(topic, 3)

    msg = cl.Message(content="")
    await msg.stream_token(f"Downloading documents regarding {topic}.\n")
    for doc in documents:
        download_pdf(doc['pdf_url'], 'downloads', doc['title'] + '.pdf')
        await msg.stream_token(f"Document '{doc['title']}' downloaded successfully!\n")


    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-exp"
        # model_name="gemini-2.0-pro-exp-02-05",
        )

    folder_path = "downloads"
    file_paths = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, file))]
    files = []
    for file_path in file_paths:
        print(file_path)
        files.append(
        upload_to_gemini(file_path, mime_type="application/pdf"),
        )

    wait_for_files_active(files)

    parts = []
    for i in range(len(files)):
        parts.append(files[i])
    parts.append("""You have knowledge in these documnets.
                     You will answer questions based on these documents. 
                     You will ALWAYS search in ALL 3 documents provided 
                     and you will answer as accurately as possible.""")

    chat = model.start_chat(history=[
    {
        "role": "user",
        "parts": parts,
    }])

    await msg.stream_token("""\nI can now provide information regarding the documents above. 
                                What would you like to know?""")
    await msg.send()

    return chat
